import sys
import can
from .config import CAN_INTERFACE

def run_monitor():
    print(f"Starting Low-Level CAN Monitor on {CAN_INTERFACE}...")

    try:
        # Initialize CAN bus
        bus = can.interface.Bus(channel=CAN_INTERFACE, interface='socketcan')

        print("Monitoring raw frames. Press Ctrl+C to stop.")
        print(f"{'ID':<10} | {'DLC':<5} | {'DATA'}")
        print("-" * 30)

        while True:
            msg = bus.recv(timeout=1.0)

            if msg is None:
                continue

            # Format data as hex bytes
            data_hex = ' '.join(f"{b:02X}" for b in msg.data)

            print(f"0x{msg.arbitration_id:03X}    | {msg.dlc:<5} | {data_hex}")

    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")
    except Exception as e:
        print(f"\nMonitor error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_monitor()
