import time
import sys
import cantools
import can
from datetime import datetime
from .config import CAN_INTERFACE, DBC_FILE_PATH

def run_receiver():
    print(f"Starting CAN Receiver on {CAN_INTERFACE}...")

    try:
        # Load DBC
        db = cantools.database.load_file(DBC_FILE_PATH)

        # Initialize CAN bus
        bus = can.interface.Bus(channel=CAN_INTERFACE, interface='socketcan')

        print("Receiver listening. Press Ctrl+C to stop.")
        print("-" * 60)

        while True:
            # Receive CAN frame
            msg = bus.recv(timeout=1.0)

            if msg is None:
                continue

            # Decode using DBC
            try:
                decoded_data = db.decode_message(msg.arbitration_id, msg.data)
                msg_info = db.get_message_by_frame_id(msg.arbitration_id)

                # Format output
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{timestamp}] ID=0x{msg.arbitration_id:03X} {msg_info.name}")

                for signal_name, value in decoded_data.items():
                    # Find signal definition for unit
                    sig = next((s for s in msg_info.signals if s.name == signal_name), None)
                    unit = sig.unit if sig else ""
                    print(f"  {signal_name}={value} {unit}")

                print() # Newline for readability

            except KeyError:
                # Message ID not in DBC
                pass
            except Exception as e:
                print(f"Error decoding message ID 0x{msg.arbitration_id:03X}: {e}")

    except KeyboardInterrupt:
        print("\nReceiver stopped by user.")
    except Exception as e:
        print(f"\nReceiver error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_receiver()
