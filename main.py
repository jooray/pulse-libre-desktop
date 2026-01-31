import asyncio
import os
import logging

# Suppress debug logging
os.environ["KIVY_LOG_LEVEL"] = "info"
logging.getLogger("bleak").setLevel(logging.WARNING)

from bleak import BleakScanner, BleakClient
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ListProperty, ColorProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.graphics import Color, RoundedRectangle, Ellipse, Line
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.animation import Animation
from kivy.core.text import LabelBase
import threading


def get_font():
    """Get an available font with fallbacks. Roboto is bundled with Kivy."""
    # Try system fonts first, fall back to Kivy's bundled Roboto
    system_fonts = ['Helvetica', 'Arial', 'DejaVuSans']
    for font in system_fonts:
        try:
            LabelBase.register(f'_test_{font}', f'{font}.ttf')
            return font
        except Exception:
            pass
    # Roboto is always available as it's bundled with Kivy
    return 'Roboto'


FONT_NAME = get_font()

# Constants for BLE communication
DEVICE_NAME_PREFIX = "Pulsetto"
UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # Write
UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Notify

# Battery voltage constants
BATTERY_FULL_VOLTAGE = 3.95  # Voltage at 100%
BATTERY_EMPTY_VOLTAGE = 2.5  # Voltage at 0%

# Modern color scheme - Dark theme (professional medical/wellness aesthetic)
COLORS = {
    'bg_dark': '#0F1419',
    'bg_card': '#1A1F2E',
    'bg_card_light': '#252B3D',
    'text_primary': '#FFFFFF',
    'text_secondary': '#9CA3AF',
    'text_muted': '#6B7280',
    'accent_blue': '#3B82F6',
    'accent_blue_light': '#60A5FA',
    'accent_green': '#10B981',
    'accent_red': '#EF4444',
    'accent_orange': '#F59E0B',
    'divider': '#374151',
    'button_bg': '#374151',
    'progress_bg': '#374151',
}

class Card(FloatLayout):
    """A rounded card widget with shadow effect"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.padding = dp(24)
        with self.canvas.before:
            Color(rgba=get_color_from_hex(COLORS['bg_card']))
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
        self.bind(pos=self._update_rect, size=self._update_rect)
    
    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

class StatusIndicator(BoxLayout):
    """Connection status indicator with dot and label"""
    connected = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.spacing = dp(6)
        self.size_hint = (1, None)
        self.height = dp(24)

        # Container to center content
        with self.canvas:
            self.dot_color = Color(rgba=get_color_from_hex(COLORS['accent_red']))
            self.dot = Ellipse(size=(dp(8), dp(8)))

        self.label = Label(
            text='Disconnected',
            font_size=sp(14),
            color=get_color_from_hex(COLORS['text_primary']),
            font_name=FONT_NAME,
            bold=True,
            size_hint=(1, 1),
            halign='center',
            valign='middle'
        )
        self.label.bind(size=self.label.setter('text_size'))
        self.add_widget(self.label)
        self.bind(pos=self._update_dot, size=self._update_dot)
        self.label.bind(texture_size=self._update_dot)

    def _update_dot(self, *args):
        # Position dot to the left of the text
        if self.label.texture_size[0] > 0:
            text_width = self.label.texture_size[0]
            dot_x = self.center_x - text_width / 2 - dp(14)
            self.dot.pos = (dot_x, self.center_y - dp(4))

    def on_connected(self, instance, value):
        if value:
            self.dot_color.rgba = get_color_from_hex(COLORS['accent_green'])
            self.label.text = 'Connected'
        else:
            self.dot_color.rgba = get_color_from_hex(COLORS['accent_red'])
            self.label.text = 'Disconnected'
        self._update_dot()

class CircularButton(Button):
    """A circular button with modern styling"""
    def __init__(self, text='', **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.font_size = sp(28)
        self.bold = False
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.size_hint = (None, None)
        self.size = (dp(56), dp(56))
        self.color = get_color_from_hex(COLORS['text_primary'])
        
        with self.canvas.before:
            Color(rgba=get_color_from_hex(COLORS['button_bg']))
            self.circle = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=self._update_graphics, size=self._update_graphics)
    
    def _update_graphics(self, *args):
        self.circle.pos = self.pos
        self.circle.size = self.size
    
    def on_press(self):
        anim = Animation(opacity=0.7, duration=0.1)
        anim.start(self)
    
    def on_release(self):
        anim = Animation(opacity=1, duration=0.1)
        anim.start(self)

class CustomProgressBar(Widget):
    """Custom progress bar with rounded corners"""
    progress = NumericProperty(0)  # 0 to 100
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, None)
        self.height = dp(4)
        
        with self.canvas:
            # Background
            Color(rgba=get_color_from_hex(COLORS['progress_bg']))
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(2)])
            # Progress fill
            Color(rgba=get_color_from_hex(COLORS['accent_blue_light']))
            self.fill_rect = RoundedRectangle(pos=self.pos, size=(0, self.height), radius=[dp(2)])
        
        self.bind(pos=self._update_graphics, size=self._update_graphics, progress=self._update_progress)
    
    def _update_graphics(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self._update_progress()
    
    def _update_progress(self, *args):
        width = self.width * (self.progress / 100)
        self.fill_rect.pos = self.pos
        self.fill_rect.size = (width, self.height)

class ModernSlider(BoxLayout):
    """A modern styled slider with labels"""
    value = NumericProperty(5)
    min = NumericProperty(1)
    max = NumericProperty(9)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.spacing = dp(12)
        self.size_hint = (1, None)
        self.height = dp(40)
        
        self.min_label = Label(
            text=str(int(self.min)),
            font_size=sp(14),
            color=get_color_from_hex(COLORS['text_muted']),
            size_hint=(None, 1),
            width=dp(24)
        )
        self.add_widget(self.min_label)
        
        self.slider = Slider(
            min=self.min,
            max=self.max,
            value=self.value,
            step=1,
            size_hint=(1, 1),
            cursor_size=(dp(20), dp(20)),
            cursor_image='',
            cursor_disabled_image='',
            background_width=dp(4),
        )
        self.slider.bind(value=self._on_value_change)
        self.add_widget(self.slider)
        
        self.max_label = Label(
            text=str(int(self.max)),
            font_size=sp(14),
            color=get_color_from_hex(COLORS['text_muted']),
            size_hint=(None, 1),
            width=dp(24)
        )
        self.add_widget(self.max_label)
        
        # Style the slider
        with self.slider.canvas.before:
            Color(rgba=get_color_from_hex(COLORS['progress_bg']))
            self.slider.bg_rect = RoundedRectangle(pos=self.slider.pos, size=self.slider.size, radius=[dp(2)])
        
        with self.slider.canvas:
            Color(rgba=get_color_from_hex(COLORS['accent_blue']))
            self.slider.fill_rect = RoundedRectangle(pos=self.slider.pos, size=(0, dp(4)), radius=[dp(2)])
        
        self.slider.bind(pos=self._update_slider_graphics, size=self._update_slider_graphics, value=self._update_slider_graphics)
    
    def _on_value_change(self, instance, value):
        self.value = int(value)
    
    def _update_slider_graphics(self, *args):
        if hasattr(self.slider, 'bg_rect'):
            padding = dp(16)
            self.slider.bg_rect.pos = (self.slider.x + padding, self.slider.center_y - dp(2))
            self.slider.bg_rect.size = (self.slider.width - padding * 2, dp(4))
        
        if hasattr(self.slider, 'fill_rect'):
            padding = dp(16)
            ratio = (self.slider.value - self.slider.min) / (self.slider.max - self.slider.min)
            fill_width = (self.slider.width - padding * 2) * ratio
            self.slider.fill_rect.pos = (self.slider.x + padding, self.slider.center_y - dp(2))
            self.slider.fill_rect.size = (fill_width, dp(4))

class MainButton(Button):
    """Large main action button with rounded corners"""
    button_type = StringProperty('start')  # start, stop, scan
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_size = sp(20)
        self.bold = True
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.size_hint = (1, None)
        self.height = dp(64)
        self.color = get_color_from_hex(COLORS['text_primary'])
        
        with self.canvas.before:
            self.bg_color = Color(rgba=get_color_from_hex(COLORS['accent_green']))
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(32)])

        self.bind(pos=self._update_graphics, size=self._update_graphics)
        self.on_button_type(self, self.button_type)
    
    def _update_graphics(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
    
    def on_button_type(self, instance, value):
        if not hasattr(self, 'bg_color'):
            return
        if value == 'start':
            self.bg_color.rgba = get_color_from_hex(COLORS['accent_green'])
            self.text = 'Start'
        elif value == 'stop':
            self.bg_color.rgba = get_color_from_hex(COLORS['accent_red'])
            self.text = 'Stop'
        elif value == 'scan':
            self.bg_color.rgba = get_color_from_hex(COLORS['accent_blue'])
            self.text = 'Scan for Device'
        elif value == 'scanning':
            self.bg_color.rgba = get_color_from_hex(COLORS['accent_blue'])
            self.text = 'Scanning...'
    
    def on_press(self):
        anim = Animation(opacity=0.8, duration=0.1)
        anim.start(self)
    
    def on_release(self):
        anim = Animation(opacity=1, duration=0.1)
        anim.start(self)

class StrengthBadge(BoxLayout):
    """Badge displaying strength value"""
    value = NumericProperty(5)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(80), dp(56))
        self.padding = [dp(24), dp(12)]
        
        with self.canvas.before:
            Color(rgba=get_color_from_hex(COLORS['accent_blue']))
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(24)])
        
        self.label = Label(
            text=str(self.value),
            font_size=sp(32),
            color=get_color_from_hex(COLORS['text_primary']),
            bold=True,
            font_name=FONT_NAME
        )
        self.add_widget(self.label)
        self.bind(pos=self._update_graphics, size=self._update_graphics, value=self._update_value)
    
    def _update_graphics(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
    
    def _update_value(self, *args):
        self.label.text = str(self.value)

class MainScreen(BoxLayout):
    timer_text = StringProperty("10:00")
    battery_level = StringProperty("--")
    charging_status = StringProperty("Not Charging")
    strength = NumericProperty(5)  # Default to 5
    is_running = BooleanProperty(False)
    device_connected = BooleanProperty(False)
    device_found = BooleanProperty(False)
    timer_minutes = NumericProperty(10)  # Default to 10 minutes

    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(orientation="vertical", **kwargs)
        self.padding = dp(16)
        self.spacing = dp(16)
        
        self.remaining_time = self.timer_minutes * 60  # Convert minutes to seconds
        self.timer_event = None
        self.client = None
        self.loop_thread = AsyncioLoopThread()
        self.loop = self.loop_thread.loop
        self.keepalive_counter = 0
        self.status_poll_event = None

        # Build UI
        self._build_status_bar()
        self._build_timer_card()
        self._build_strength_card()
        self._build_control_button()

        # Start BLE operations
        self.loop_thread.run_coroutine(self.ble_loop())

    def _build_status_bar(self):
        """Build the status bar at the top"""
        status_bar = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(80),
            padding=[dp(20), dp(16)],
            spacing=dp(8)
        )
        
        with status_bar.canvas.before:
            Color(rgba=get_color_from_hex(COLORS['bg_card']))
            self.status_rect = RoundedRectangle(pos=status_bar.pos, size=status_bar.size, radius=[dp(12)])
        status_bar.bind(pos=self._update_status_rect, size=self._update_status_rect)
        
        # Connection status
        conn_box = self._create_status_item('Connection')
        self.status_indicator = StatusIndicator()
        conn_box.add_widget(self.status_indicator)
        status_bar.add_widget(conn_box)
        
        # Divider
        status_bar.add_widget(self._create_divider())
        
        # Battery
        battery_box = self._create_status_item('Battery')
        self.battery_label = Label(
            text='--',
            font_size=sp(14),
            color=get_color_from_hex(COLORS['text_primary']),
            bold=True,
            size_hint=(1, None),
            height=dp(20)
        )
        battery_box.add_widget(self.battery_label)
        status_bar.add_widget(battery_box)
        
        # Divider
        status_bar.add_widget(self._create_divider())
        
        # Charging
        charging_box = self._create_status_item('Charging')
        self.charging_label = Label(
            text='--',
            font_size=sp(14),
            color=get_color_from_hex(COLORS['text_primary']),
            bold=True,
            size_hint=(1, None),
            height=dp(20)
        )
        charging_box.add_widget(self.charging_label)
        status_bar.add_widget(charging_box)
        
        self.add_widget(status_bar)
    
    def _create_status_item(self, label_text):
        box = BoxLayout(orientation='vertical', size_hint=(1, 1))
        label = Label(
            text=label_text,
            font_size=sp(12),
            color=get_color_from_hex(COLORS['text_secondary']),
            size_hint=(1, None),
            height=dp(18)
        )
        box.add_widget(label)
        return box
    
    def _create_divider(self):
        divider = Widget(size_hint=(None, 1), width=dp(1))
        with divider.canvas:
            Color(rgba=get_color_from_hex(COLORS['divider']))
            self.divider_rect = RoundedRectangle(pos=divider.pos, size=divider.size)
        divider.bind(pos=self._update_divider, size=self._update_divider)
        return divider
    
    def _update_status_rect(self, instance, value):
        self.status_rect.pos = instance.pos
        self.status_rect.size = instance.size
    
    def _update_divider(self, instance, value):
        self.divider_rect.pos = instance.pos
        self.divider_rect.size = instance.size

    def _build_timer_card(self):
        """Build the timer card"""
        timer_card = BoxLayout(
            orientation='vertical',
            size_hint=(1, None),
            height=dp(160),
            padding=dp(24),
            spacing=dp(16)
        )
        
        with timer_card.canvas.before:
            Color(rgba=get_color_from_hex(COLORS['bg_card']))
            self.timer_rect = RoundedRectangle(pos=timer_card.pos, size=timer_card.size, radius=[dp(16)])
        timer_card.bind(pos=self._update_timer_rect, size=self._update_timer_rect)
        
        # Label
        timer_label = Label(
            text='Session Timer',
            font_size=sp(16),
            color=get_color_from_hex(COLORS['text_secondary']),
            bold=True,
            size_hint=(1, None),
            height=dp(24)
        )
        timer_card.add_widget(timer_label)
        
        # Timer display row
        timer_row = BoxLayout(orientation='horizontal', spacing=dp(24))
        
        # Decrease button
        self.decrease_button = CircularButton(text='-')
        self.decrease_button.bind(on_press=self.decrease_timer)
        timer_row.add_widget(self.decrease_button)
        
        # Timer value
        timer_value_box = BoxLayout(orientation='vertical', size_hint=(1, 1))
        self.timer_display = Label(
            text=self.timer_text,
            font_size=sp(56),
            color=get_color_from_hex(COLORS['text_primary']),
            bold=True,
            font_name=FONT_NAME,
            size_hint=(1, None),
            height=dp(70)
        )
        timer_value_box.add_widget(self.timer_display)
        
        # Progress bar
        self.timer_progress = CustomProgressBar(size_hint=(1, None), height=dp(4))
        self.timer_progress.progress = 0
        timer_value_box.add_widget(self.timer_progress)
        
        timer_row.add_widget(timer_value_box)
        
        # Increase button
        self.increase_button = CircularButton(text='+')
        self.increase_button.bind(on_press=self.increase_timer)
        timer_row.add_widget(self.increase_button)
        
        timer_card.add_widget(timer_row)
        self.add_widget(timer_card)
    
    def _update_timer_rect(self, instance, value):
        self.timer_rect.pos = instance.pos
        self.timer_rect.size = instance.size

    def _build_strength_card(self):
        """Build the strength control card"""
        strength_card = BoxLayout(
            orientation='vertical',
            size_hint=(1, None),
            height=dp(180),
            padding=dp(24),
            spacing=dp(16)
        )
        
        with strength_card.canvas.before:
            Color(rgba=get_color_from_hex(COLORS['bg_card']))
            self.strength_rect = RoundedRectangle(pos=strength_card.pos, size=strength_card.size, radius=[dp(16)])
        strength_card.bind(pos=self._update_strength_rect, size=self._update_strength_rect)
        
        # Label
        strength_label = Label(
            text='Intensity Level',
            font_size=sp(16),
            color=get_color_from_hex(COLORS['text_secondary']),
            bold=True,
            size_hint=(1, None),
            height=dp(24)
        )
        strength_card.add_widget(strength_label)
        
        # Strength display row
        strength_row = BoxLayout(orientation='horizontal', spacing=dp(24))

        # Decrease button
        self.strength_minus = CircularButton(text='-')
        self.strength_minus.bind(on_press=lambda x: self.change_strength(-1))
        strength_row.add_widget(self.strength_minus)

        # Center container to hold badge (AnchorLayout centers content)
        center_box = AnchorLayout(size_hint=(1, 1), anchor_x='center', anchor_y='center')
        self.strength_badge = StrengthBadge(value=self.strength)
        center_box.add_widget(self.strength_badge)
        strength_row.add_widget(center_box)

        # Increase button
        self.strength_plus = CircularButton(text='+')
        self.strength_plus.bind(on_press=lambda x: self.change_strength(1))
        strength_row.add_widget(self.strength_plus)

        strength_card.add_widget(strength_row)
        
        # Slider
        self.strength_slider = ModernSlider(value=self.strength)
        self.strength_slider.slider.bind(value=self.on_strength_change)
        strength_card.add_widget(self.strength_slider)
        
        self.add_widget(strength_card)
    
    def _update_strength_rect(self, instance, value):
        self.strength_rect.pos = instance.pos
        self.strength_rect.size = instance.size

    def _build_control_button(self):
        """Build the main control button"""
        self.main_button = MainButton(button_type='scan')
        self.main_button.bind(on_press=self.main_button_pressed)
        self.add_widget(Widget(size_hint=(1, 1)))  # Spacer
        self.add_widget(self.main_button)

    def change_strength(self, delta):
        """Change strength by delta amount"""
        new_value = max(1, min(9, self.strength + delta))
        self.strength = new_value
        self.strength_slider.slider.value = new_value
        self.strength_badge.value = new_value
        if self.is_running:
            self.loop_thread.run_coroutine(self.send_command(f"{int(self.strength)}\n"))

    def main_button_pressed(self, instance):
        if not self.device_connected:
            self.loop_thread.run_coroutine(self.scan_and_connect())
        elif not self.is_running:
            self.start_session()
        else:
            self.stop_session()

    def start_session(self):
        if not self.device_connected:
            return
        self.is_running = True
        self.start_timer()
        self.loop_thread.run_coroutine(self.start_device())
        self._update_button_state()

    def stop_session(self):
        self.is_running = False
        self.stop_timer()
        self.loop_thread.run_coroutine(self.stop_device())
        self._update_button_state()

    def _update_button_state(self):
        """Update button appearance based on state"""
        if not self.device_connected:
            self.main_button.button_type = 'scan'
            self.decrease_button.disabled = False
            self.decrease_button.opacity = 1
            self.increase_button.disabled = False
            self.increase_button.opacity = 1
        elif self.is_running:
            self.main_button.button_type = 'stop'
            self.decrease_button.disabled = True
            self.decrease_button.opacity = 0.3
            self.increase_button.disabled = True
            self.increase_button.opacity = 0.3
        else:
            self.main_button.button_type = 'start'
            self.decrease_button.disabled = False
            self.decrease_button.opacity = 1
            self.increase_button.disabled = False
            self.increase_button.opacity = 1

    async def ble_loop(self):
        self.set_button_scanning()
        await self.scan_for_device()
        if self.device_found:
            await self.connect_to_device()
            if self.device_connected:
                await self.query_device()
        self.update_ui()

    async def scan_and_connect(self):
        self.set_button_scanning()
        await self.scan_for_device()
        if self.device_found:
            await self.connect_to_device()
            if self.device_connected:
                await self.query_device()
        self.update_ui()

    async def scan_for_device(self):
        self.device_found = False
        self.device_address = None
        try:
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

    async def connect_to_device(self):
        if self.device_address:
            self.client = BleakClient(self.device_address)
            try:
                await self.client.connect()
                print("Connected to device.")
                self.device_connected = True

                # Start notification handler
                await self.client.start_notify(UART_TX_CHAR_UUID, self.notification_handler)

                # Handle disconnection
                self.client.set_disconnected_callback(self.on_disconnected)

                # Start periodic status polling
                Clock.schedule_once(lambda dt: self.start_status_polling(), 0)
            except Exception as e:
                print(f"Failed to connect: {e}")
                self.device_connected = False

    def on_disconnected(self, client):
        print("Device disconnected.")
        was_running = self.is_running
        self.device_connected = False
        self.stop_status_polling()
        self.schedule_ui_update()

        # Attempt to reconnect
        self.loop_thread.run_coroutine(self.attempt_reconnect(was_running))

    async def attempt_reconnect(self, was_running):
        print("Attempting to reconnect...")
        await asyncio.sleep(2)  # Wait before retry
        await self.scan_for_device()
        if self.device_found:
            await self.connect_to_device()
            if self.device_connected:
                await self.query_device()
                # Resume session if it was running
                if was_running and self.is_running and self.remaining_time > 0:
                    print("Resuming session after reconnection...")
                    await self.start_device()
        self.schedule_ui_update()

    def start_status_polling(self):
        if self.status_poll_event:
            self.status_poll_event.cancel()
        self.status_poll_event = Clock.schedule_interval(self.poll_status, 30)

    def poll_status(self, dt):
        if self.device_connected:
            self.loop_thread.run_coroutine(self.query_device())

    def stop_status_polling(self):
        if self.status_poll_event:
            self.status_poll_event.cancel()
            self.status_poll_event = None

    async def query_device(self):
        await self.send_command("Q\n")  # Get battery level
        await self.send_command("u\n")  # Get charging status

    @mainthread
    def schedule_ui_update(self):
        self.update_ui()

    @mainthread
    def set_button_scanning(self):
        self.main_button.button_type = 'scanning'

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
        self.keepalive_counter = 0
        self.update_timer_label()
        self.timer_event = Clock.schedule_interval(self.update_timer, 1)

    def stop_timer(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None
        self.remaining_time = self.timer_minutes * 60
        self.timer_progress.progress = 0
        self.update_timer_label()

    def update_timer(self, dt):
        if self.remaining_time > 0:
            self.remaining_time -= 1
            self.update_timer_label()

            # Update progress bar
            total_time = self.timer_minutes * 60
            progress = ((total_time - self.remaining_time) / total_time) * 100
            self.timer_progress.progress = progress

            # Send keep-alive every 10 seconds
            self.keepalive_counter += 1
            if self.keepalive_counter % 10 == 0:
                self.loop_thread.run_coroutine(self.send_command(f"{int(self.strength)}\n"))
        else:
            self.is_running = False
            self.stop_timer()
            self.loop_thread.run_coroutine(self.stop_device())
            self._update_button_state()

    def update_timer_label(self):
        mins, secs = divmod(self.remaining_time, 60)
        self.timer_text = f"{mins:02d}:{secs:02d}"
        self.timer_display.text = self.timer_text

    def on_strength_change(self, instance, value):
        self.strength = int(value)
        self.strength_badge.value = self.strength
        if self.is_running:
            # Send the new strength command when the device is running
            self.loop_thread.run_coroutine(self.send_command(f"{int(self.strength)}\n"))

    def update_ui(self):
        # Update battery display
        self.battery_label.text = self.battery_level if self.battery_level != "--" else "--"
        
        # Update charging display
        if self.charging_status == "Charging":
            self.charging_label.text = "Yes"
        elif self.charging_status == "Not Charging":
            self.charging_label.text = "No"
        else:
            self.charging_label.text = "--"
        
        # Update connection indicator
        self.status_indicator.connected = self.device_connected
        
        # Update button state
        self._update_button_state()

    def decrease_timer(self, instance):
        if self.timer_minutes > 1 and not self.is_running:
            self.timer_minutes -= 1
            self.remaining_time = self.timer_minutes * 60
            self.update_timer_label()

    def increase_timer(self, instance):
        if not self.is_running:
            self.timer_minutes += 1
            self.remaining_time = self.timer_minutes * 60
            self.update_timer_label()

    def on_stop(self):
        # Called when the app is closing
        if self.client and self.client.is_connected:
            self.loop_thread.run_coroutine(self.client.disconnect())
        self.loop_thread.stop()


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


class PulseLibreApp(App):
    def build(self):
        self.title = 'Pulse Libre'
        # Set window background color
        from kivy.core.window import Window
        Window.clearcolor = get_color_from_hex(COLORS['bg_dark'])
        
        self.main_screen = MainScreen()
        return self.main_screen

    def on_stop(self):
        self.main_screen.on_stop()


if __name__ == '__main__':
    PulseLibreApp().run()
