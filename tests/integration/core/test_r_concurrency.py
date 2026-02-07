import asyncio
import pytest
import os
import shutil
from pathlib import Path
from rmcp.core.context import Context, LifespanState
from rmcp.r_integration import execute_r_script_async

@pytest.mark.asyncio
async def test_r_concurrency_and_rdata_integrity():
    """
    Test that concurrent R execution for the same session does not corrupt .RData.
    The per-session lock should serialize requests, and atomic save in R should
    prevent workspace corruption.
    """
    # Clean up any existing test session data
    session_id = "concurrency_test_session"
    exports_dir = Path.cwd() / "exports"
    session_dir = exports_dir / session_id
    if session_dir.exists():
        shutil.rmtree(session_dir)

    lifespan = LifespanState(r_session_enabled=True)
    
    # Create multiple contexts with the same session_id
    contexts = []
    for i in range(5):
        ctx = Context.create(f"req_{i}", "test", lifespan)
        ctx.set_r_session_id(session_id)
        contexts.append(ctx)

    # Initial script to set up a counter in the workspace
    setup_script = """
    counter <- 0
    result <- list(status = "initialized", counter = counter)
    """
    await execute_r_script_async(setup_script, {}, contexts[0])

    # Concurrent script that increments the counter
    # The script loads .RData (implicitly), increments counter, and saves (implicitly)
    # Adding a sleep in R to increase the likelihood of catching races if locks fail.
    increment_script = """
    # Counter should be loaded from .RData
    if (!exists("counter")) {
        counter <- 0
    }
    
    # Artificial delay to simulate work and increase race condition probability
    Sys.sleep(0.5)
    
    counter <- counter + 1
    result <- list(counter = counter)
    """

    # Run 10 increments concurrently
    # With a concurrency of 4 (R_SEMAPHORE), this will take some time but should be safe.
    # The session lock should serialize all 10 calls for this specific session.
    tasks = [
        execute_r_script_async(increment_script, {}, contexts[i % 5])
        for i in range(10)
    ]
    
    print("Starting 10 concurrent R increments...")
    results = await asyncio.gather(*tasks)
    
    # If locking works, the final counter value should be 10
    final_check_script = """
    result <- list(final_counter = counter)
    """
    final_result = await execute_r_script_async(final_check_script, {}, contexts[0])
    
    print(f"Final counter value: {final_result['final_counter']}")
    
    # Verify that all increments were recorded
    assert final_result['final_counter'] == 10
    
    # Verify that each task saw a unique counter value from 1 to 10
    observed_counters = sorted([r['counter'] for r in results])
    assert observed_counters == list(range(1, 11))
    print("✅ Concurrency test passed: counter is correct and no corruption occurred.")

@pytest.mark.asyncio
async def test_r_multi_session_concurrency():
    """
    Test that different sessions can run concurrently (up to R_SEMAPHORE limit)
    and don't block each other.
    """
    lifespan = LifespanState(r_session_enabled=True)
    
    # Create 4 contexts with DIFFERENT session_ids
    contexts = []
    for i in range(4):
        ctx = Context.create(f"req_{i}", "test", lifespan)
        ctx.set_r_session_id(f"session_{i}")
        contexts.append(ctx)
        # Clean up existing data
        session_dir = Path.cwd() / "exports" / f"session_{i}"
        if session_dir.exists():
            shutil.rmtree(session_dir)

    # Script that sleeps for 1 second in R
    sleep_script = """
    Sys.sleep(1)
    result <- list(status = "slept")
    """

    start_time = asyncio.get_event_loop().time()
    
    # Run 4 different sessions concurrently. 
    # Since R_SEMAPHORE is 4, they should all start around the same time.
    # Total time should be slightly more than 1 second, NOT 4 seconds.
    tasks = [
        execute_r_script_async(sleep_script, {}, ctx)
        for ctx in contexts
    ]
    
    print("Starting 4 multi-session R scripts...")
    await asyncio.gather(*tasks)
    
    end_time = asyncio.get_event_loop().time()
    duration = end_time - start_time
    
    print(f"Total duration for 4 concurrent sessions: {duration:.2f}s")
    
    # It should take roughly 1s + overhead, definitely less than 3s.
    assert duration < 3.0 
    print("✅ Multi-session concurrency test passed: sessions ran in parallel.")

if __name__ == "__main__":
    asyncio.run(test_r_concurrency_and_rdata_integrity())
