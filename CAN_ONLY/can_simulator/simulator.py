import time
import sys
import cantools
import can
from .config import CAN_INTERFACE, DBC_FILE_PATH, SEND_INTERVAL
from .signal_model import EngineTelemetryModel

def run_simulator():
    print(f"Starting CAN Simulator on {CAN_INTERFACE}...")

    try:
        # Load DBC
        db = cantools.database.load_file(DBC_FILE_PATH)

        # Initialize CAN bus
        bus = can.interface.Bus(channel=CAN_INTERFACE, interface='socketcan')

        # Initialize Telemetry Model
        model = EngineTelemetryModel()

        print("Simulator running. Press Ctrl+C to stop.")
        print("-" * 50)

        while True:
            # Update telemetry state
            model.update()
            data = model.get_telemetry()

            # Encode and send messages
            # We iterate over the messages defined in the DBC that start with 0x100 (256)
            for msg in db.messages:
                msg_id = msg.frame_id
                if 256 <= msg_id <= 262:
                    # Filter data for this specific message
                    msg_signals = {sig.name: data.get(sig.name, 0) for sig in msg.signals}

                    try:
                        can_data = db.encode_message(msg.name, msg_signals)
                        can_msg = can.Message(
                            arbitration_id=msg_id,
                            data=can_data,
                            is_extended_id=False
                        )
                        bus.send(can_msg)
                    except Exception as e:
                        print(f"Error encoding/sending message {msg.name}: {e}")

            # Print a concise status line every few cycles
            if int(time.time() * 10) % 10 == 0:
                print(f"Transmitting telemetry: RPM={data['RPM']} | Throttle={data['Throttle']}% | Alt={data['Altitude']}m", end='\r')

            time.sleep(SEND_INTERVAL)

    except KeyboardInterrupt:
        print("\nSimulator stopped by user.")
    except Exception as e:
        print(f"\nSimulator error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_simulator()
