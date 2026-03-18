import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
import time
from datetime import datetime
import queue
import json
import urllib.request
import urllib.parse
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("Warning: RPi.GPIO not available. GPIO functions will be simulated.")

try:
    import pyodbc
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("Warning: pyodbc not available. Database functions will be disabled.")


class PullTesterApp:
    """Main application class for Pull Tester"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Pull Tester")
        self.root.geometry("1360x768") 
        # GPIO Pin Configuration
        self.PIN_LED = 17
        self.PIN_START = 18
        self.PIN_STOP = 23
        
        # Serial Configuration
        self.serial_port = None
        self.serial_device = '/dev/ttyUSB0'
        self.baud_rate = 19200

        self.arduino_port = None 
        self.arduino_device = '/dev/ttyUSB1'
        self.arduino_baud_rate = 9600
        
        self.arduino_queue = queue.Queue()

        # Application State
        self.buffer = ""
        self.arduino_buffer = ""
        self.continue_mode = False
        self.measuring = False
        self.step = 0
        self.measure = 0
        self.time_start = None
        
        # Data storage
        self.current_force = 0.0
        self.max_force = 0.0
        self.wire_size = ""
        self.wire_type = ""
        self.side_a = ""
        self.side_b = ""
        self.shift = ""
        self.barcode = ""
        self.selected_machine = ""
        self.standard = 0.0
        self.next_terminal = ""
        self.api_step = 0
        self.api_complete = False
        
        # Chart data
        self.chart_times = []
        self.chart_forces = []
        self._chart_line = None         
        self._last_chart_draw = 0       
        self._chart_draw_interval = 0.2 
        self._last_force_text = None    
        self._last_max_fg = None        
        
        # Threading
        self.serial_queue = queue.Queue()
        self.running = True
        
        # Serial reconnection
        self.serial_connected = False
        self.reconnect_attempts = 0
        
        # Database connection
        self.db_conn = None
        
        # Test history (in-memory storage)
        self.test_history = []
        
        # Initialize components
        self.init_gpio()
        self.init_ui()  # Create UI first (includes status_bar)
        self.init_serial()  # Then initialize serial (uses status_bar)
        self.init_database()
        
        # Start serial reader thread
        self.serial_thread = threading.Thread(target=self.serial_reader_thread, daemon=True)
        self.serial_thread.start()
        
        self.arduino_thread = threading.Thread(target=self.arduino_reader_thread, daemon=True)
        self.arduino_thread.start()

        # Start timer for processing serial data
        self.process_queue()
        self.process_arduino_queue()

        # Initialize device
        self.initialize_device()
        
    def init_gpio(self):
        """Initialize GPIO pins"""
        if GPIO_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.PIN_LED, GPIO.OUT)
                GPIO.setup(self.PIN_START, GPIO.OUT)
                GPIO.setup(self.PIN_STOP, GPIO.OUT)
                GPIO.output(self.PIN_LED, GPIO.LOW)
                GPIO.output(self.PIN_START, GPIO.LOW)
                GPIO.output(self.PIN_STOP, GPIO.LOW)
                print("GPIO initialized successfully")
            except Exception as e:
                print(f"GPIO initialization error: {e}")
        else:
            print("GPIO not available - running in simulation mode")
    
    def init_serial(self):
        """Initialize serial port connection"""
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                
            self.serial_port = serial.Serial(
                port=self.serial_device,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            self.serial_connected = True
            self.reconnect_attempts = 0
            print(f"Serial port {self.serial_device} opened successfully")
            if hasattr(self, 'status_bar'):
                self.status_bar.config(text=f"Connected to {self.serial_device}")
        except Exception as e:
            self.serial_connected = False
            print(f"Serial port error: {e}")
            if hasattr(self, 'status_bar'):
                self.status_bar.config(text=f"Serial Error: {e} - Running in simulation mode")
            self.serial_port = None

        try:
            self.arduino_port = serial.Serial(
                port=self.arduino_device,
                baudrate=self.arduino_baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            print(f"Arduino serial port {self.arduino_device} opened successfully")
        except Exception as e:
            
            print(f"Arduino port error: {e}")
            self.arduino_port = None 
    
    def init_database(self):
        """Initialize database connection"""
        if not DB_AVAILABLE:
            return
            
        try:
            # Configure your database connection here
            connection_string = (
                'DRIVER={ODBC Driver 17 for SQL Server};'
                'SERVER=your_server;'
                'DATABASE=your_database;'
                'UID=your_username;'
                'PWD=your_password'
            )
        
            # self.db_conn = pyodbc.connect(connection_string)
            # print("Database connected successfully")
        except Exception as e:
            print(f"Database connection error: {e}")
    
    def init_ui(self):
        """Initialize the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)  # Only one main row now
        
        # Left panel - Lot input
        self.create_lot_panel(main_frame)
        
        # Right panel - Test controls and display
        self.create_control_panel(main_frame)
        
        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
    
    def create_lot_panel(self, parent):
        """Create lot number input panel"""
        lot_frame = ttk.LabelFrame(parent, text="Input Lot", padding="10")
        lot_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))

        ttk.Label(lot_frame, text="Lot Number:", font=('Arial', 11)).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        self.lot_entry = ttk.Entry(lot_frame, width=20, font=('Arial', 11))
        self.lot_entry.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        self.lot_entry.bind('<Return>', lambda e: self.validate_lot())

        self.btn_ok = tk.Button(
            lot_frame, text="OK", font=('Arial', 12, 'bold'),
            bg='#2196F3', fg='white', width=14, height=2,
            command=self.validate_lot
        )
        self.btn_ok.grid(row=2, column=0, columnspan=2, pady=(0, 10))

        self.lot_status_lbl = ttk.Label(lot_frame, text="", font=('Arial', 10), wraplength=180)
        self.lot_status_lbl.grid(row=3, column=0, columnspan=2, sticky=tk.W)

    def validate_lot(self):
        """Validate lot number via API and populate test information"""
        lot_number = self.lot_entry.get().strip()
        if not lot_number:
            self.lot_status_lbl.config(text="Please enter a lot number.", foreground='orange')
            return

        self.lot_status_lbl.config(text="Checking lot number...", foreground='gray')
        self.btn_ok.config(state='disabled')

        def fetch():
            try:
                url = f"http://122.144.4.194:81/ApiTensionCek/get_data.php?barcode={urllib.parse.quote(lot_number)}"
                req = urllib.request.Request(url, headers={'User-Agent': 'PullTester/1.0'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw = resp.read().decode('utf-8', errors='ignore')
                self.root.after(0, lambda: self._handle_lot_response(raw, lot_number))
            except Exception as e:
                self.root.after(0, lambda err=e: self._handle_lot_error(str(err)))

        threading.Thread(target=fetch, daemon=True).start()

    def _handle_lot_response(self, raw, lot_number):
        """Process API response for lot validation"""
        self.btn_ok.config(state='normal')
        try:
            response = json.loads(raw)

            if not response.get('status', False):
                raise ValueError("invalid lot")

            data = response.get('data')
            if not data or not isinstance(data, dict):
                raise ValueError("empty data")

            kode_mesin = data.get('kode_mesin') or ''
            ukuran     = data.get('ukuran') or ''
            wire       = data.get('wire') or ''
            std        = data.get('standard') or 0

            if not kode_mesin and not ukuran:
                raise ValueError("invalid lot")

            self.side_a        = str(response.get('terminal_a') or '')
            self.side_b        = str(response.get('terminal_b') or '')
            self.next_terminal = str(response.get('next_terminal') or 'A').upper()
            self.api_step      = int(response.get('step') or 1)
            self.api_complete  = bool(response.get('complete', False))

            self.selected_machine = str(kode_mesin)
            self.wire_size        = str(ukuran)
            self.wire_type        = str(wire)
            self.barcode          = lot_number
            try:
                self.standard = float(std)
            except (ValueError, TypeError):
                self.standard = 0.0

            self.lbl_machine.config(text=self.selected_machine)
            self.lbl_barcode.config(text=self.barcode)
            self.lbl_wire_size.config(text=self.wire_size)
            self.lbl_standard.config(text=f"{self.standard:.2f}")

            if self.next_terminal == 'B':
                self.combo_side.current(1)
            else:
                self.combo_side.current(0)

            if self.api_complete:
                self.lot_status_lbl.config(
                    text="✓ All terminals tested — lot complete.", foreground='blue')
                self.btn_start.config(state='disabled')
            else:
                self.lot_status_lbl.config(
                    text=f"✓ Lot valid! Test terminal {self.next_terminal} (step {self.api_step})",
                    foreground='green')
                self.btn_start.config(state='normal')

            if self.serial_port and self.standard > 0:
                self.send_setpoint()

            if hasattr(self, 'status_bar'):
                self.status_bar.config(
                    text=f"Lot: {lot_number} | Machine: {self.selected_machine} | Next terminal: {self.next_terminal}")

        except Exception as e:
            print(f"Lot response error: {e}")
            self._handle_lot_invalid()

    def _handle_lot_invalid(self):
        """Show error for invalid lot"""
        self.btn_ok.config(state='normal')
        self.lot_status_lbl.config(
            text="✗ Lot number is invalid.\nPlease re-enter the lot number.",
            foreground='red'
        )
        self.selected_machine = ""
        self.wire_size = ""
        self.wire_type = ""
        self.barcode = ""
        self.standard = 0.0
        self.next_terminal = ""
        self.api_step = 0
        self.api_complete = False
        self.lbl_machine.config(text="")
        self.lbl_barcode.config(text="")
        self.lbl_wire_size.config(text="")
        self.lbl_standard.config(text="")
        self.lot_entry.select_range(0, tk.END)
        self.lot_entry.focus()

    def _handle_lot_error(self, error_msg):
        """Show network/connection error"""
        self.btn_ok.config(state='normal')
        self.lot_status_lbl.config(
            text=f"✗ Connection error.\nCheck network and try again.",
            foreground='red'
        )
        print(f"Lot API error: {error_msg}")

    
    def create_control_panel(self, parent):
        """Create test control panel"""
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Info group
        info_group = ttk.LabelFrame(control_frame, text="Test Information", padding="10")
        info_group.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Machine label
        ttk.Label(info_group, text="Machine:").grid(row=0, column=0, sticky=tk.W)
        self.lbl_machine = ttk.Label(info_group, text="", font=('Arial', 12, 'bold'))
        self.lbl_machine.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        # Barcode
        ttk.Label(info_group, text="Lot Number:").grid(row=1, column=0, sticky=tk.W)
        self.lbl_barcode = ttk.Label(info_group, text="", font=('Arial', 10))
        self.lbl_barcode.grid(row=1, column=1, sticky=tk.W, padx=10)
        
        # Wire size
        ttk.Label(info_group, text="Wire Size:").grid(row=2, column=0, sticky=tk.W)
        self.lbl_wire_size = ttk.Label(info_group, text="", font=('Arial', 10))
        self.lbl_wire_size.grid(row=2, column=1, sticky=tk.W, padx=10)
        
        # Terminal selection
        ttk.Label(info_group, text="Terminal Side:").grid(row=3, column=0, sticky=tk.W)
        self.combo_side = ttk.Combobox(info_group, values=["Terminal A", "Terminal B"], state='readonly', width=15)
        self.combo_side.current(0)
        self.combo_side.grid(row=3, column=1, sticky=tk.W, padx=10)
        #self.combo_side.bind('<<ComboboxSelected>>', self.on_side_change)
        
        # Terminal label
        self.lbl_terminal = ttk.Label(info_group, text="", font=('Arial', 10))
        self.lbl_terminal.grid(row=3, column=2, sticky=tk.W, padx=10)
        
        # Standard
        ttk.Label(info_group, text="Standard (Kgf):").grid(row=4, column=0, sticky=tk.W)
        self.lbl_standard = ttk.Label(info_group, text="", font=('Arial', 10))
        self.lbl_standard.grid(row=4, column=1, sticky=tk.W, padx=10)
        
        # Test History button
        self.btn_history = tk.Button(info_group, text="Test History", font=('Arial', 11, 'bold'),
                                     bg='green', fg='white', width=18, height=1,
                                     command=self.show_history_window)
        self.btn_history.grid(row=5, column=0, columnspan=3, pady=10, padx=5)
        
        # Measurement group
        measure_group = ttk.LabelFrame(control_frame, text="Measurement", padding="10")
        measure_group.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
        
        # Current force
        ttk.Label(measure_group, text="Current Force (Kgf):").grid(row=0, column=0, sticky=tk.W)
        self.lbl_current = ttk.Label(measure_group, text="0.00", font=('Arial', 16, 'bold'), foreground='black')
        self.lbl_current.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        # Max force
        ttk.Label(measure_group, text="Max Force (Kgf):").grid(row=1, column=0, sticky=tk.W)
        self.lbl_max = ttk.Label(measure_group, text="0.00", font=('Arial', 16, 'bold'), foreground='black')
        self.lbl_max.grid(row=1, column=1, sticky=tk.W, padx=10)
        
        # Result panel
        self.result_panel = tk.Label(measure_group, text="", font=('Arial', 20, 'bold'), 
                                     width=10, height=2, bg='white', relief=tk.RAISED)
        self.result_panel.grid(row=2, column=0, columnspan=2, pady=10)
        
        # Start button
        self.btn_start = tk.Button(measure_group, text="START TEST", font=('Arial', 14, 'bold'),
                                   bg='green', fg='white', width=20, height=2,
                                   command=self.start_test)
        self.btn_start.grid(row=3, column=0, columnspan=2, pady=10)
        
        # Reconnect button (for serial port issues)
        self.btn_reconnect = tk.Button(measure_group, text="Reconnect Imada Serial", font=('Arial', 10),
                                       bg='orange', fg='white', width=20,
                                       command=self.manual_reconnect)
        self.btn_reconnect.grid(row=4, column=0, columnspan=2, pady=5)
        
        # Chart
        chart_group = ttk.LabelFrame(control_frame, text="Force Chart", padding="10")
        chart_group.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))
        
        self.fig = Figure(figsize=(6, 4), dpi=72)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Force (Kgf)')
        self.ax.set_title('Pull Test Chart')
        self.ax.grid(True)
        self._chart_line, = self.ax.plot([], [], 'b-')  # reuse, never re-plot
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_group)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def create_data_panel(self, parent):
        """Create data grid panel"""
        data_frame = ttk.LabelFrame(parent, text="Test History", padding="10")
        data_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        
        # Date filter
        filter_frame = ttk.Frame(data_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Date:").pack(side=tk.LEFT, padx=(0, 5))
        self.date_entry = ttk.Entry(filter_frame, width=15)
        self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.date_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(filter_frame, text="Refresh", command=self.refresh_data).pack(side=tk.LEFT)
        
        # Treeview
        columns = ('Time', 'Barcode', 'Wire', 'Terminal A', 'Terminal B', 'Force', 'Status')
        self.tree = ttk.Treeview(data_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def select_machine(self, machine_num):
        """Legacy method - no longer used with lot-based workflow"""
        pass
    
    def load_machine_data(self):
        """Legacy method - data now loaded via lot number API"""
        pass
    
    def send_setpoint(self):
        """Send setpoint to force gauge"""
        if self.serial_port and self.standard > 0:
            # Format: XCW+4000+XXXX where XXXX is standard * 100
            setpoint = int(self.standard * 100)
            setpoint_str = f"{setpoint:04d}"
            command = f"XCW+4000+{setpoint_str}\r"
            self.write_serial(command)
    
    def start_test(self):
        """Start a pull test"""
        if self.measuring:
            return
        
        # Clear result
        self.result_panel.config(text="", bg='white')
        
        # Reset chart
        self.chart_times.clear()
        self.chart_forces.clear()
        self._chart_line.set_data([], [])
        self.ax.autoscale(True)
        self._last_chart_draw = 0
        self.canvas.draw_idle()
        
        # Reset measurements
        self.measuring = True
        self.measure = 0
        self.max_force = 0.0
        self.lbl_max.config(text="0.00", foreground='white')
        self.btn_start.config(state='disabled')
        
        # Send zero command
        self.write_serial('Z\r')
        self.write_arduino(b'start\n')
        # Trigger start signal
        self.trigger_gpio(self.PIN_START)
        
        # Update status
        if hasattr(self, 'status_bar'):
            self.status_bar.config(text="Test in progress...")
    
    def manual_reconnect(self):
        """Manually reconnect serial — background thread so UI stays responsive"""
        self.btn_reconnect.config(state='disabled', text='Reconnecting...')
        if hasattr(self, 'status_bar'):
            self.status_bar.config(text="Reconnecting to serial port...")

        def _do_reconnect():
            port = self.serial_port
            self.serial_connected = False
            self.serial_port = None
            if port:
                try:
                    port.close()
                except Exception:
                    pass
            self.reconnect_attempts = 0
            self.init_serial()
            self.continue_mode = False
            self.step = 0
            if self.serial_connected:
                self.root.after(0, self._reconnect_success)
            else:
                self.root.after(0, self._reconnect_failed)

        threading.Thread(target=_do_reconnect, daemon=True).start()

    def _reconnect_success(self):
        self.btn_reconnect.config(state='normal', text='Reconnect Imada Serial')
        self.initialize_device()
        messagebox.showinfo("Reconnect", "Serial port reconnected successfully!")

    def _reconnect_failed(self):
        self.btn_reconnect.config(state='normal', text='Reconnect Imada Serial')
        messagebox.showwarning("Reconnect", "Failed to reconnect. Check cable and try again.")
    
    def trigger_gpio(self, pin):
        """Trigger a GPIO pin (pulse)"""
        if GPIO_AVAILABLE:
            try:
                GPIO.output(pin, GPIO.HIGH)
                threading.Timer(0.25, lambda: GPIO.output(pin, GPIO.LOW)).start()
            except Exception as e:
                print(f"GPIO trigger error: {e}")
        else:
            print(f"GPIO trigger simulated for pin {pin}")
    
    def write_serial(self, data):
        """Write data to serial port"""
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(data.encode('ascii'))
            except serial.SerialException as e:
                print(f"Serial write error (disconnected): {e}")
                self.serial_connected = False
                self.serial_port = None
            except Exception as e:
                print(f"Serial write error: {e}")
        else:
            print(f"Serial write (not connected): {data.strip()}")
    
    def write_arduino(self, data: bytes):
        """
        Kirim perintah bytes ke Arduino via serial.
        data harus bertipe bytes, contoh: b'start\\n' atau b'stop\\n'
        """
        if self.arduino_port and self.arduino_port.is_open:
            try:
                self.arduino_port.write(data)
                print(f"Arduino << {data}")
            except Exception as e:
                print(f"Serial write error (Arduino): {e}")
        else:
            print(f"Arduino write simulated: {data}")

    # ✅ FIX: Thread reader khusus Arduino
    def arduino_reader_thread(self):
        """Background thread membaca balasan dari Arduino"""
        while self.running:
            if self.arduino_port and self.arduino_port.is_open:
                try:
                    if self.arduino_port.in_waiting:
                        data = self.arduino_port.read(self.arduino_port.in_waiting)
                        self.arduino_queue.put(data.decode('ascii', errors='ignore'))
                except Exception as e:
                    print(f"Serial read error (Arduino): {e}")
            time.sleep(0.01)

    # ✅ FIX: Proses queue balasan dari Arduino
    def process_arduino_queue(self):
        """Proses data yang diterima dari Arduino"""
        try:
            while not self.arduino_queue.empty():
                data = self.arduino_queue.get_nowait()
                self.arduino_buffer += data

                # Proses setiap baris yang diakhiri '\n'
                while '\n' in self.arduino_buffer:
                    line, self.arduino_buffer = self.arduino_buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        self.handle_arduino_message(line)
        except queue.Empty:
            pass

        self.root.after(10, self.process_arduino_queue)

    # ✅ FIX: Handler pesan dari Arduino
    def handle_arduino_message(self, message: str):
        """
        Proses pesan yang diterima dari Arduino.
        Contoh pesan yang mungkin dikirim Arduino:
          'ready'  → Arduino siap
          'started' → Arduino konfirmasi mulai
          'stopped' → Arduino konfirmasi berhenti
          'error'  → Arduino melaporkan error
        """
        print(f"Arduino >> {message}")
        msg = message.lower()

        if msg == "ready":
            self.lbl_arduino_status.config(text="Ready ✔", foreground="green")
        elif msg == "started":
            self.lbl_arduino_status.config(text="Running ▶", foreground="blue")
        elif msg == "stopped":
            self.lbl_arduino_status.config(text="Stopped ■", foreground="gray")
        elif msg == "error":
            self.lbl_arduino_status.config(text="Error ✘", foreground="red")
        else:
            # Tampilkan pesan lain apa adanya
            self.lbl_arduino_status.config(text=message, foreground="black")


    def serial_reader_thread(self):
        """Background thread to read serial data"""
        while self.running:
            # Try to reconnect if disconnected
            if not self.serial_connected or not self.serial_port or not self.serial_port.is_open:
                if self.reconnect_attempts < 5:  # Try 5 times before giving up
                    self.reconnect_attempts += 1
                    print(f"Attempting to reconnect... (attempt {self.reconnect_attempts}/5)")
                    try:
                        self.init_serial()
                        if self.serial_connected:
                            print("Reconnected successfully!")
                    except:
                        pass
                time.sleep(5)  # Wait before retry
                continue
            
            # Read data if connected
            if self.serial_port and self.serial_port.is_open:
                try:
                    if self.serial_port.in_waiting:
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        self.serial_queue.put(data.decode('ascii', errors='ignore'))
                        self.serial_connected = True
                        self.reconnect_attempts = 0
                except serial.SerialException as e:
                    print(f"Serial connection lost: {e}")
                    self.serial_connected = False
                    if self.serial_port:
                        try:
                            self.serial_port.close()
                        except:
                            pass
                    self.serial_port = None
                except Exception as e:
                    print(f"Serial read error: {e}")
            time.sleep(0.01)
    
    def process_queue(self):
        """Process serial data from queue"""
        try:
            while not self.serial_queue.empty():
                data = self.serial_queue.get_nowait()
                self.process_serial_data(data)
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(10, self.process_queue)
    
    def process_serial_data(self, data):
        """Process received serial data"""
        self.buffer += data
        
        if self.buffer.endswith('\r'):
            self.handle_serial_message(self.buffer.strip())
            self.buffer = ""
    
    def handle_serial_message(self, message):
        """Handle complete serial message"""
        if not self.continue_mode:
            # Initialization sequence
            if self.step == 0 and message.startswith('R'):
                self.step = 1
            elif self.step == 1 and message.startswith('R'):
                self.write_serial('K\r')  # Set Kgf units
                self.step = 2
            elif self.step == 2 and message.startswith('R'):
                self.write_serial('XAg\r')  # Continue
                self.step = 0
                self.continue_mode = True
                self.lbl_max.config(text="0.00")
        else:
            # Normal operation
            if message.startswith('l'):
                # Live force reading: lXX.XXX
                force_str = message[1:7]
                try:
                    force = float(force_str)
                    self.current_force = force

                    # Only update label when value visibly changes
                    ft = f"{force:.2f}"
                    if ft != self._last_force_text:
                        self._last_force_text = ft
                        self.lbl_current.config(text=ft)

                    if self.measuring:
                        if force >= 0.1 and self.measure == 0:
                            self.measure = 1
                            self.time_start = datetime.now()
                            self.lbl_max.config(foreground='white')
                            self._last_max_fg = 'white'

                        if self.measure == 1:
                            # Update max force color only when it changes
                            new_fg = 'lime' if self.max_force >= self.standard else 'red'
                            if new_fg != self._last_max_fg:
                                self.lbl_max.config(foreground=new_fg)
                                self._last_max_fg = new_fg

                            if self.max_force < force:
                                self.max_force = force
                                self.lbl_max.config(text=f"{self.max_force:.2f}")
                            else:
                                self.write_serial('XFP\r')

                            elapsed = (datetime.now() - self.time_start).total_seconds() * 1000
                            self.chart_times.append(elapsed)
                            self.chart_forces.append(force)

                            # Throttled redraw — at most every 150 ms
                            now = time.monotonic()
                            if now - self._last_chart_draw >= self._chart_draw_interval:
                                self._last_chart_draw = now
                                self._chart_line.set_data(self.chart_times, self.chart_forces)
                                self.ax.relim()
                                self.ax.autoscale(True)
                                self.ax.autoscale_view()
                                self.canvas.draw_idle()

                            if force <= 0.1 and self.max_force > 1:
                                self.finish_test()
                
                except ValueError:
                    pass
            
            elif message.startswith('p'):
                # Peak force: pXX.XXX
                force_str = message[1:7]
                try:
                    force = float(force_str)
                    if self.max_force < force:
                        self.max_force = force
                        self.lbl_max.config(text=f"{self.max_force:.2f}")
                except ValueError:
                    pass
    
    def finish_test(self):
        """Finish the test and save results"""
        self.measure = 0
        self.measuring = False
        self.btn_start.config(state='disabled')

        self.trigger_gpio(self.PIN_STOP)

        tested_terminal = "A" if self.combo_side.current() == 0 else "B"

        if self.max_force >= self.standard:
            status = "OK"
            self.result_panel.config(text="OK", bg='lime', fg='black')
        else:
            status = "NG"
            self.result_panel.config(text="NG", bg='red', fg='white')

        current_time = datetime.now()

        # Store force per terminal slot
        force_a = f"{self.max_force:.2f}" if tested_terminal == 'A' else ''
        force_b = f"{self.max_force:.2f}" if tested_terminal == 'B' else ''

        self.write_arduino(b'stop\n')

        test_result = {
            'time':      current_time.strftime('%H:%M:%S'),
            'datetime':  current_time,
            'barcode':   self.barcode,
            'machine':   self.selected_machine,
            'wire_type': self.wire_type,
            'wire_size': self.wire_size,
            'standard':  f"{self.standard:.2f}",
            'force_a':   force_a,
            'force_b':   force_b,
            'terminal':  tested_terminal,
            'status':    status,
        }
        self.test_history.insert(0, test_result)
        if len(self.test_history) > 100:
            self.test_history = self.test_history[:100]

        self.save_test_result(status)
        self.refresh_data()

        if hasattr(self, 'status_bar'):
            self.status_bar.config(
                text=f"Test done: {status} | Terminal {tested_terminal}: {self.max_force:.2f} Kgf | Sending to API...")

        # POST result to insert API in background then re-fetch lot
        threading.Thread(
            target=self._post_test_result,
            args=(self.barcode, tested_terminal, self.max_force,
                  self.selected_machine, self.wire_type, self.wire_size, self.standard),
            daemon=True
        ).start()
    
    def _post_test_result(self, barcode, terminal, nilai, kode_mesin, type_wire, size_wire, standard):
        """POST test result to insert API (background thread)"""
        try:
            params = urllib.parse.urlencode({
                'barcode':    barcode,
                'terminal':   terminal,
                'nilai':      f"{nilai:.2f}",
                'kode_mesin': kode_mesin,
                'type_wire':  type_wire,
                'size_wire':  size_wire,
                'standard':   f"{standard:.2f}",
            })
            url = f"http://122.144.4.194:81/ApiTensionCek/insert_data.php?{params}"
            req = urllib.request.Request(url, headers={'User-Agent': 'PullTester/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode('utf-8', errors='ignore')
            print(f"Insert API response: {raw}")
            self.root.after(0, lambda: self._refetch_lot_after_test(barcode))
        except Exception as e:
            print(f"Insert API error: {e}")
            self.root.after(0, lambda err=str(e): self._post_result_failed(err))

    def _refetch_lot_after_test(self, barcode):
        """Re-fetch lot to get updated terminal status after a test"""
        self.lot_status_lbl.config(text="Updating lot status...", foreground='gray')

        def fetch():
            try:
                url = f"http://122.144.4.194:81/ApiTensionCek/get_data.php?barcode={urllib.parse.quote(barcode)}"
                req = urllib.request.Request(url, headers={'User-Agent': 'PullTester/1.0'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw = resp.read().decode('utf-8', errors='ignore')
                self.root.after(0, lambda: self._handle_lot_response(raw, barcode))
            except Exception as e:
                self.root.after(0, lambda err=e: self._handle_lot_error(str(err)))

        threading.Thread(target=fetch, daemon=True).start()

    def _post_result_failed(self, error_msg):
        """Handle failed POST — show warning but re-enable start button"""
        if hasattr(self, 'status_bar'):
            self.status_bar.config(text=f"⚠ API insert failed: {error_msg}")
        self.btn_start.config(state='normal')

    def save_test_result(self, status):
        """Save test result to database"""
        if not self.db_conn:
            print(f"Test result (not saved): {status}, Force: {self.max_force:.2f} Kgf")
            return
        
        try:
            cursor = self.db_conn.cursor()
            
            machine_code = self.selected_machine.replace('CNC', 'CSM')
            terminal_a = self.side_a if self.combo_side.current() == 0 else ''
            terminal_b = self.side_b if self.combo_side.current() == 1 else ''
            
            query = """
            INSERT INTO dbo.TrRPHTARIKWIRE 
            (tanggal, sift, kodemesin, Barcode, ukuranwire, terminala, terminalb, testarik, StatusTarik)
            VALUES (GETDATE(), ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            cursor.execute(query, (
                1,  # shift
                machine_code,
                self.barcode,
                self.wire_size,
                terminal_a,
                terminal_b,
                f"{self.max_force:.2f}",
                status
            ))
            
            self.db_conn.commit()
            print("Test result saved to database")
            
        except Exception as e:
            print(f"Database save error: {e}")
    
    def show_history_window(self):
        """Show test history with calendar date picker + API fetch"""
        import calendar as _cal

        history_window = tk.Toplevel(self.root)
        history_window.title("Test History")
        history_window.geometry("1100x700")
        history_window.resizable(True, True)

        main_frame = ttk.Frame(history_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(2, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # ── Title ──────────────────────────────────────────────────────────
        tk.Label(main_frame, text="Test History",
                 font=('Arial', 15, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))

        # ── Date picker panel ──────────────────────────────────────────────
        picker_frame = ttk.LabelFrame(main_frame, text="Select Date", padding="8")
        picker_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8))

        # State vars — default to today; will be overwritten by server date
        now = datetime.now()
        sel_year  = tk.IntVar(value=now.year)
        sel_month = tk.IntVar(value=now.month)
        sel_day   = tk.IntVar(value=now.day)

        MONTHS = ['January','February','March','April','May','June',
                  'July','August','September','October','November','December']

        # Navigation row
        nav_frame  = ttk.Frame(picker_frame)
        nav_frame.pack(fill=tk.X)
        month_lbl  = tk.Label(nav_frame, font=('Arial', 11, 'bold'), width=22)
        cal_frame  = ttk.Frame(picker_frame)

        def _draw_calendar():
            yr  = sel_year.get()
            mo  = sel_month.get()
            day = sel_day.get()
            month_lbl.config(text=f"{MONTHS[mo-1]}  {yr}")
            for w in cal_frame.winfo_children():
                w.destroy()
            for c, h in enumerate(['Mo','Tu','We','Th','Fr','Sa','Su']):
                tk.Label(cal_frame, text=h, width=4,
                         font=('Arial', 9, 'bold'), fg='#555').grid(row=0, column=c)
            first_wd, days_in_month = _cal.monthrange(yr, mo)
            row, col = 1, first_wd
            for d in range(1, days_in_month + 1):
                is_sel = (d == day)
                tk.Button(
                    cal_frame, text=str(d), width=4,
                    bg='#2196F3' if is_sel else '#f0f0f0',
                    fg='white'   if is_sel else 'black',
                    relief=tk.FLAT, font=('Arial', 9),
                    command=lambda _d=d: _pick_day(_d)
                ).grid(row=row, column=col, padx=1, pady=1)
                col += 1
                if col > 6:
                    col = 0
                    row += 1

        def _pick_day(day):
            sel_day.set(day)
            _draw_calendar()
            _fetch_history()

        def _prev_month():
            mo = sel_month.get() - 1
            yr = sel_year.get()
            if mo < 1:
                mo, yr = 12, yr - 1
            sel_month.set(mo)
            sel_year.set(yr)
            sel_day.set(1)
            _draw_calendar()

        def _next_month():
            mo = sel_month.get() + 1
            yr = sel_year.get()
            if mo > 12:
                mo, yr = 1, yr + 1
            sel_month.set(mo)
            sel_year.set(yr)
            sel_day.set(1)
            _draw_calendar()

        tk.Button(nav_frame, text='◀', command=_prev_month,
                  font=('Arial', 11), relief=tk.FLAT, bg='#e0e0e0').pack(side=tk.LEFT)
        month_lbl.pack(side=tk.LEFT, padx=6)
        tk.Button(nav_frame, text='▶', command=_next_month,
                  font=('Arial', 11), relief=tk.FLAT, bg='#e0e0e0').pack(side=tk.LEFT)
        cal_frame.pack(pady=(6, 0))

        # Status row below calendar
        status_row = ttk.Frame(picker_frame)
        status_row.pack(fill=tk.X, pady=(6, 0))
        date_lbl    = ttk.Label(status_row, text="", font=('Arial', 10, 'bold'))
        date_lbl.pack(side=tk.LEFT, padx=(0, 10))
        fetch_status = ttk.Label(status_row, text="Loading server date…", font=('Arial', 9), foreground='gray')
        fetch_status.pack(side=tk.LEFT)
        ttk.Button(status_row, text="↺ Refresh",
                   command=lambda: _fetch_history()).pack(side=tk.RIGHT)

        # ── Table ──────────────────────────────────────────────────────────
        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=2, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        columns = ('Time', 'Barcode', 'Machine', 'Wire Type', 'Wire Size',
                   'Standard (Kgf)', 'Terminal A (Kgf)', 'Terminal B (Kgf)', 'Status')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        col_widths = {
            'Time': 80, 'Barcode': 130, 'Machine': 75,
            'Wire Type': 130, 'Wire Size': 75, 'Standard (Kgf)': 100,
            'Terminal A (Kgf)': 115, 'Terminal B (Kgf)': 115, 'Status': 70,
        }
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=col_widths.get(col, 90), anchor=tk.CENTER)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,   command=tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.E, tk.W))
        tree.tag_configure('ok', foreground='green', font=('Arial', 9, 'bold'))
        tree.tag_configure('ng', foreground='red',   font=('Arial', 9, 'bold'))

        # ── Summary + bottom bar ───────────────────────────────────────────
        bottom = ttk.Frame(main_frame)
        bottom.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(8, 0))
        lbl_total = ttk.Label(bottom, text="Total: 0",   font=('Arial', 10, 'bold'))
        lbl_ok    = ttk.Label(bottom, text="OK: 0",      font=('Arial', 10, 'bold'), foreground='green')
        lbl_ng    = ttk.Label(bottom, text="NG: 0",      font=('Arial', 10, 'bold'), foreground='red')
        lbl_pct   = ttk.Label(bottom, text="Pass: 0.0%", font=('Arial', 10, 'bold'))
        for lbl in (lbl_total, lbl_ok, lbl_ng, lbl_pct):
            lbl.pack(side=tk.LEFT, padx=12)

        api_rows = []   # holds last fetched records for export

        # ── Helpers ────────────────────────────────────────────────────────
        def _row_val(r, *keys):
            for k in keys:
                v = r.get(k)
                if v is not None:
                    return str(v)
            return ''

        def _populate(rows):
            for item in tree.get_children():
                tree.delete(item)
            if not rows:
                tree.insert('', tk.END,
                    values=('No data for this date','','','','','','','',''))
                lbl_total.config(text="Total: 0")
                lbl_ok.config(text="OK: 0")
                lbl_ng.config(text="NG: 0")
                lbl_pct.config(text="Pass: 0.0%")
                return
            ok_n = 0
            for r in rows:
                status = _row_val(r, 'status', 'StatusTarik').upper()
                if status == 'OK':
                    ok_n += 1
                tree.insert('', tk.END,
                    tags=('ok' if status == 'OK' else 'ng',),
                    values=(
                        _row_val(r, 'time', 'jam', 'created_at', 'tanggal'),
                        _row_val(r, 'barcode', 'Barcode'),
                        _row_val(r, 'kode_mesin', 'kodemesin', 'machine'),
                        _row_val(r, 'type_wire', 'wire', 'wire_type'),
                        _row_val(r, 'ukuran', 'size_wire', 'ukuranwire', 'wire_size'),
                        _row_val(r, 'standard', 'std'),
                        _row_val(r, 'terminal_a', 'terminala', 'force_a'),
                        _row_val(r, 'terminal_b', 'terminalb', 'force_b'),
                        status,
                    ))
            total = len(rows)
            ng    = total - ok_n
            pct   = ok_n / total * 100 if total else 0
            lbl_total.config(text=f"Total: {total}")
            lbl_ok.config(text=f"OK: {ok_n}")
            lbl_ng.config(text=f"NG: {ng}")
            lbl_pct.config(text=f"Pass: {pct:.1f}%")

        def _fetch_history():
            yr  = sel_year.get()
            mo  = sel_month.get()
            day = sel_day.get()
            date_str = f"{yr:04d}-{mo:02d}-{day:02d}"
            date_lbl.config(text=f"Date: {day:02d}/{mo:02d}/{yr}")
            fetch_status.config(text="Fetching…", foreground='gray')

            def _do():
                try:
                    params = urllib.parse.urlencode({'start': date_str, 'end': date_str})
                    url = f"http://122.144.4.194:81/ApiTensionCek/get_history.php?{params}"
                    req = urllib.request.Request(url, headers={'User-Agent': 'PullTester/1.0'})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        raw = resp.read().decode('utf-8', errors='ignore')
                    history_window.after(0, lambda: _on_history(raw))
                except Exception as e:
                    history_window.after(0,
                        lambda err=str(e): fetch_status.config(
                            text=f"✗ Network error: {err}", foreground='red'))

            threading.Thread(target=_do, daemon=True).start()

        def _on_history(raw):
            nonlocal api_rows
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    rows = data
                elif isinstance(data, dict):
                    rows = data.get('data', [])
                    if isinstance(rows, dict):
                        rows = [rows]
                else:
                    rows = []
                api_rows = rows
                _populate(rows)
                fetch_status.config(
                    text=f"✓ {len(rows)} record(s) loaded", foreground='green')
            except Exception as e:
                fetch_status.config(text=f"✗ Parse error: {e}", foreground='red')

        # ── Step 1: get server date, then fetch history ────────────────────
        def _load_server_date():
            try:
                url = "http://122.144.4.194:81/ApiTensionCek/get_time.php"
                req = urllib.request.Request(url, headers={'User-Agent': 'PullTester/1.0'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw = resp.read().decode('utf-8', errors='ignore')
                history_window.after(0, lambda: _on_server_date(raw))
            except Exception:
                # Fall back to local date and still fetch history
                history_window.after(0, _fetch_history)

        def _on_server_date(raw):
            try:
                data = json.loads(raw)
                date_str = data.get('server_time') or data.get('date') or data.get('tanggal') or ''
                # expect YYYY-MM-DD
                parts = date_str.split('-')
                if len(parts) == 3:
                    sel_year.set(int(parts[0]))
                    sel_month.set(int(parts[1]))
                    sel_day.set(int(parts[2]))
                    _draw_calendar()
            except Exception:
                pass  # keep local date
            _fetch_history()

        threading.Thread(target=_load_server_date, daemon=True).start()
        _draw_calendar()  # draw immediately with local date while waiting

        # ── Export ─────────────────────────────────────────────────────────
        def _export():
            try:
                import csv
                fname = (f"history_{sel_year.get()}"
                         f"{sel_month.get():02d}{sel_day.get():02d}.csv")
                with open(fname, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Time','Barcode','Machine','Wire Type','Wire Size',
                                     'Standard (Kgf)','Terminal A (Kgf)','Terminal B (Kgf)','Status'])
                    for r in api_rows:
                        status = _row_val(r, 'status', 'StatusTarik').upper()
                        writer.writerow([
                            _row_val(r, 'time', 'jam', 'created_at', 'tanggal'),
                            _row_val(r, 'barcode', 'Barcode'),
                            _row_val(r, 'kode_mesin', 'kodemesin', 'machine'),
                            _row_val(r, 'type_wire', 'wire', 'wire_type'),
                            _row_val(r, 'ukuran', 'size_wire', 'ukuranwire', 'wire_size'),
                            _row_val(r, 'standard', 'std'),
                            _row_val(r, 'terminal_a', 'terminala', 'force_a'),
                            _row_val(r, 'terminal_b', 'terminalb', 'force_b'),
                            status,
                        ])
                messagebox.showinfo("Export", f"Saved to {fname}", parent=history_window)
            except Exception as e:
                messagebox.showerror("Export Error", str(e), parent=history_window)

        ttk.Button(bottom, text="Export CSV", command=_export).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom, text="Close",
                   command=history_window.destroy).pack(side=tk.RIGHT)
    
    def refresh_data(self):
        """Refresh the data - history is now shown in popup window"""
        # Data is stored in self.test_history
        # History window has its own refresh function
        pass
    
    def initialize_device(self):
        """Initialize the force gauge device (background thread — never block main)"""
        def _init():
            if self.serial_port:
                self.write_serial('Y\r')
                time.sleep(0.5)
        threading.Thread(target=_init, daemon=True).start()
    
    def cleanup(self):
        """Cleanup resources on exit"""
        self.running = False
        
        if self.serial_port:
            try:
                if self.serial_port.is_open:
                    self.write_serial('Y\r')
                    time.sleep(0.1)
                    self.serial_port.close()
                    print("Serial port closed")

                if self.arduino_port and self.arduino_port.is_open:
                   self.arduino_port.close()
                   print("Arduino serial port closed.") 
                    
            except Exception as e:
                print(f"Error closing serial port: {e}")
        
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
                print("GPIO cleaned up")
            except Exception as e:
                print(f"Error cleaning GPIO: {e}")
        
        if self.db_conn:
            try:
                self.db_conn.close()
                print("Database connection closed")
            except Exception as e:
                print(f"Error closing database: {e}")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = PullTesterApp(root)
    
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            app.cleanup()
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
