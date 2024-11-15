import asyncio
from bleak import BleakScanner, BleakClient
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.button import Button
import threading

# Constants for BLE communication
DEVICE_NAME_PREFIX = "Pulsetto"
UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # Write
UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Notify

# Battery voltage constants
BATTERY_FULL_VOLTAGE = 3.95  # Voltage at 100%
BATTERY_EMPTY_VOLTAGE = 2.5  # Voltage at 0%

class AsyncioLoopThread:
    """
    Manages a persistent asyncio event loop in a separate thread.
    """
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()

    def run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()

    def run_coroutine(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

class MainScreen(BoxLayout):
    timer_text = StringProperty("04:00")
    battery_level = StringProperty("--")
    charging_status = StringProperty("Not Charging")
    strength = NumericProperty(5)  # Default to 5
    is_running = BooleanProperty(False)
    device_connected = BooleanProperty(False)
    device_found = BooleanProperty(False)
    timer_minutes = NumericProperty(4)  # Default to 4 minutes

    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(orientation="vertical", **kwargs)
        self.remaining_time = self.timer_minutes * 60  # Convert minutes to seconds
        self.timer_event = None
        self.client = None
        self.loop_thread = AsyncioLoopThread()
        self.loop = self.loop_thread.loop

        # Layout setup
        # Timer layout with "-" and "+" buttons
        timer_layout = BoxLayout(orientation="horizontal", size_hint=(1, 0.2), padding=10, spacing=10)
        self.decrease_button = Button(text="-", font_size="24sp", size_hint=(0.2, 1))
        self.decrease_button.bind(on_press=self.decrease_timer)
        timer_layout.add_widget(self.decrease_button)

        self.timer_label = Label(text=self.timer_text, font_size="30sp", size_hint=(0.6, 1))
        timer_layout.add_widget(self.timer_label)

        self.increase_button = Button(text="+", font_size="24sp", size_hint=(0.2, 1))
        self.increase_button.bind(on_press=self.increase_timer)
        timer_layout.add_widget(self.increase_button)

        self.add_widget(timer_layout)

        # Slider layout
        slider_layout = BoxLayout(orientation="horizontal", size_hint=(1, 0.2), padding=10, spacing=10)
        self.slider = Slider(min=1, max=9, value=self.strength, step=1)
        self.slider.bind(value=self.on_strength_change)
        slider_layout.add_widget(self.slider)

        self.slider_label = Label(text=str(int(self.strength)), font_size="30sp", size_hint=(0.2, 1))
        slider_layout.add_widget(self.slider_label)

        self.add_widget(slider_layout)

        self.start_stop_button = Button(text="Start", size_hint=(1, 0.2))
        self.start_stop_button.bind(on_press=self.start_stop_button_pressed)
        self.add_widget(self.start_stop_button)

        self.status_label = Label(text="Battery: --% | Charging: --", font_size="18sp", size_hint=(1, 0.2))
        self.add_widget(self.status_label)

        self.scan_button = Button(text="Scan", size_hint=(1, 0.2))
        self.scan_button.bind(on_press=self.scan_button_pressed)
        self.add_widget(self.scan_button)

        self.update_ui()  # Initial UI update

        # Start BLE operations
        self.loop_thread.run_coroutine(self.ble_loop())

    async def ble_loop(self):
        await self.scan_for_device()
        if self.device_found:
            await self.connect_to_device()
            await self.query_device()
            self.device_connected = True
        self.update_ui()

    def scan_button_pressed(self, instance):
        self.loop_thread.run_coroutine(self.scan_and_connect())

    async def scan_and_connect(self):
        await self.scan_for_device()
        if self.device_found:
            await self.connect_to_device()
            await self.query_device()
            self.device_connected = True
            self.update_ui()

    async def scan_for_device(self):
        self.device_found = False
        self.device_address = None
        try:
            self.set_scan_button_state(scanning=True)
            devices = await BleakScanner.discover()
            for d in devices:
                if d.name and d.name.startswith(DEVICE_NAME_PREFIX):
                    self.device_address = d.address
                    self.device_found = True
                    print(f"Found device: {d.name} [{d.address}]")
                    break
            if not self.device_found:
                print("Device not found.")
        except Exception as e:
            print(f"Error during scanning: {e}")
        finally:
            self.set_scan_button_state(scanning=False)

    async def connect_to_device(self):
        if self.device_address:
            self.client = BleakClient(self.device_address)
            try:
                await self.client.connect()
                print("Connected to device.")

                # Start notification handler
                await self.client.start_notify(UART_TX_CHAR_UUID, self.notification_handler)

                # Handle disconnection
                self.client.set_disconnected_callback(self.on_disconnected)
            except Exception as e:
                print(f"Failed to connect: {e}")
                self.device_connected = False

    def on_disconnected(self, client):
        print("Device disconnected.")
        self.device_connected = False
        self.schedule_ui_update()

    async def query_device(self):
        await self.send_command("Q\n")  # Get battery level
        await self.send_command("u\n")  # Get charging status

    @mainthread
    def schedule_ui_update(self):
        self.update_ui()

    def notification_handler(self, sender, data):
        message = data.decode('utf-8').strip()
        print(f"Received: {message}")

        if "Batt:" in message:
            try:
                battery_voltage = float(message.split("Batt:")[1])
                battery_percentage = self.calculate_battery_percentage(battery_voltage)
                self.battery_level = f"{battery_percentage}%"
            except (IndexError, ValueError):
                pass
        elif message.startswith("Charging"):
            self.charging_status = "Charging"
        elif message.startswith("Not Charging"):
            self.charging_status = "Not Charging"

        self.schedule_ui_update()

    def calculate_battery_percentage(self, voltage):
        if voltage >= BATTERY_FULL_VOLTAGE:
            return 100
        elif voltage <= BATTERY_EMPTY_VOLTAGE:
            return 0
        else:
            percentage = ((voltage - BATTERY_EMPTY_VOLTAGE) / (BATTERY_FULL_VOLTAGE - BATTERY_EMPTY_VOLTAGE)) * 100
            return int(round(percentage))

    async def send_command(self, command):
        if self.client and self.client.is_connected:
            try:
                await self.client.write_gatt_char(UART_RX_CHAR_UUID, command.encode(), response=True)
                print(f"Sent command: {command.strip()}")
            except Exception as e:
                print(f"Failed to send command {command}: {e}")

    def start_stop_button_pressed(self, instance):
        if not self.is_running:
            if not self.device_connected:
                print("Device not connected.")
                return
            self.is_running = True
            self.start_stop_button.text = "Stop"
            self.start_timer()
            self.loop_thread.run_coroutine(self.start_device())
        else:
            self.is_running = False
            self.start_stop_button.text = "Start"
            self.stop_timer()
            self.loop_thread.run_coroutine(self.stop_device())

    async def start_device(self):
        await self.send_command("D\n")
        await self.send_command(f"{int(self.strength)}\n")
        print("Device started.")

    async def stop_device(self):
        await self.send_command("-\n")
        print("Device stopped.")
        # Query device status after stopping
        await self.query_device()

    def start_timer(self):
        self.remaining_time = self.timer_minutes * 60  # Convert minutes to seconds
        self.update_timer_label()
        self.timer_event = Clock.schedule_interval(self.update_timer, 1)

    def stop_timer(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None
        self.remaining_time = self.timer_minutes * 60
        self.update_timer_label()

    def update_timer(self, dt):
        if self.remaining_time > 0:
            self.remaining_time -= 1
            self.update_timer_label()
        else:
            self.is_running = False
            self.start_stop_button.text = "Start"
            self.stop_timer()
            self.loop_thread.run_coroutine(self.stop_device())

    def update_timer_label(self):
        mins, secs = divmod(self.remaining_time, 60)
        self.timer_text = f"{mins:02d}:{secs:02d}"
        self.update_ui()


    def on_strength_change(self, instance, value):
        self.strength = int(value)
        self.slider_label.text = str(self.strength)

    def update_ui(self):
        self.status_label.text = f"Battery: {self.battery_level} | Charging: {self.charging_status}"
        self.timer_label.text = self.timer_text

        if not self.device_connected:
            self.scan_button.text = "Scan"
            self.scan_button.disabled = False
            self.scan_button.opacity = 1
        else:
            # Hide the scan button when connected
            self.scan_button.opacity = 0
            self.scan_button.disabled = True

    @mainthread
    def set_scan_button_state(self, scanning):
        if scanning:
            self.scan_button.text = "Scanning for device..."
            self.scan_button.disabled = True
        else:
            if not self.device_connected:
                self.scan_button.text = "Scan"
                self.scan_button.disabled = False

    def decrease_timer(self, instance):
        if self.timer_minutes > 1:
            self.timer_minutes -= 1
            self.remaining_time = self.timer_minutes * 60  # Sync remaining time with timer minutes
            self.update_timer_label()  # Refresh the timer display immediately

    def increase_timer(self, instance):
        self.timer_minutes += 1
        self.remaining_time = self.timer_minutes * 60  # Sync remaining time with timer minutes
        self.update_timer_label()  # Refresh the timer display immediately

    def on_stop(self):
        # Called when the app is closing
        if self.client and self.client.is_connected:
            self.loop_thread.run_coroutine(self.client.disconnect())
        self.loop_thread.stop()

class PulseLibreApp(App):
    def build(self):
        self.main_screen = MainScreen()
        return self.main_screen

    def on_stop(self):
        self.main_screen.on_stop()

if __name__ == '__main__':
    PulseLibreApp().run()
