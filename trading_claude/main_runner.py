from broker_adapters import TastytradeAdapter


def main():
    adapter = TastytradeAdapter()
    
    if adapter.authenticate():
        print(f"Connected to account: {adapter.account_id}")
        # Get account balance
        balance = adapter.get_account_balance()
        print(f"Cash Balance: ${balance.get('cash_balance', 0)}")
        
        # Get positions
        positions = adapter.get_positions()
        print(f"Found {len(positions)} positions")
        
        # Get orders
        orders = adapter.get_orders()
        print(f"Found {len(orders)} orders")


if __name__ == "__main__":
    main()