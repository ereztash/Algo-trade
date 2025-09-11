# apps/strategy_loop/main.py
import asyncio
# from contracts.validators import OrderIntent

async def strategy_loop(bus):
    """
    External strategy loop that consumes market data and produces OrderIntents.
    This runs independently of the data and order planes.
    """
    print("Strategy loop started. Consuming 'market_events' and producing 'order_intents'.")
    
    # Consume normalized market events
    async for market_event in bus.consume("market_events"):
        # In a real strategy, this would be a complex process:
        # 1. Update rolling window
        # window.update(market_event)
        
        # 2. Build context and signals
        # context = build_context(window)
        # signals = build_signals(window, context)
        
        # 3. Orthogonalize and merge signals
        # mu_hat = merge_signals(signals)
        
        # 4. Solve QP for target weights
        # w_tgt = solve_qp(mu_hat, ...)
        
        # 5. Assemble and publish intents
        # intents = assemble_order_intents(w_prev, w_tgt, ...)
        # for intent in intents:
        #     await bus.publish("order_intents", intent)
        
        # Placeholder: For demonstration, we can print the event
        # print(f"Strategy received market event: {market_event}")
        pass

async def run_strategy(bus):
    await strategy_loop(bus)
