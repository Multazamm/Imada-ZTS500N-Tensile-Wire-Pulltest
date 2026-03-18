#!/usr/bin/env python3
"""
Pull Tester Demo/Test Script
Simulates serial data for testing without hardware
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
import random
from pull_tester import PullTesterApp

class DemoSerialSimulator:
    """Simulates serial port for testing"""
    
    def __init__(self, app):
        self.app = app
        self.running = False
        self.thread = None
    
    def start(self):
        """Start simulating serial data"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.simulate_data, daemon=True)
            self.thread.start()
    
    def stop(self):
        """Stop simulation"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def simulate_data(self):
        """Generate simulated serial responses"""
        # Initialization sequence
        time.sleep(0.5)
        self.app.serial_queue.put('R\r')
        time.sleep(0.5)
        self.app.serial_queue.put('R\r')
        time.sleep(0.5)
        self.app.serial_queue.put('R\r')
        
        # Continuous live data
        while self.running:
            # Simulate random force reading (format: lXX.XXX)
            if self.app.measuring and self.app.measure == 1:
                # Simulate pull test curve
                elapsed = (time.time() - self.start_time) if hasattr(self, 'start_time') else 0
                
                if elapsed < 2:
                    # Ramp up
                    force = min(5.0, elapsed * 2.5)
                elif elapsed < 4:
                    # Peak
                    force = 5.0 + random.uniform(-0.2, 0.2)
                else:
                    # Release
                    force = max(0, 5.0 - (elapsed - 4) * 2)
                
                force_str = f"l{force:06.3f}"
                self.app.serial_queue.put(force_str + '\r')
                
                # Send peak value occasionally
                if random.random() < 0.1:
                    peak_str = f"p{force:06.3f}"
                    self.app.serial_queue.put(peak_str + '\r')
            elif self.app.measuring and self.app.measure == 0:
                # Just started measuring
                self.start_time = time.time()
                self.app.serial_queue.put('l00.000\r')
            else:
                # Idle state
                self.app.serial_queue.put('l00.000\r')
            
            time.sleep(0.05)  # 20Hz update rate


def main():
    """Run demo version of Pull Tester"""
    print("=" * 50)
    print("Pull Tester - DEMO MODE")
    print("=" * 50)
    print("\nRunning in simulation mode:")
    print("- Serial data is simulated")
    print("- GPIO operations are logged")
    print("- Database is disabled")
    print("\nClick 'START TEST' to see simulated pull test")
    print("=" * 50)
    print()
    
    root = tk.Tk()
    app = PullTesterApp(root)
    
    # Disable serial port (use simulation instead)
    app.serial_port = None
    
    # Start simulator
    simulator = DemoSerialSimulator(app)
    simulator.start()
    
    # Add demo label
    demo_label = tk.Label(
        root,
        text="DEMO MODE - Simulated Data",
        bg='yellow',
        font=('Arial', 12, 'bold'),
        pady=5
    )
    demo_label.grid(row=2, column=0, sticky=(tk.W, tk.E))
    
    def on_closing():
        simulator.stop()
        app.cleanup()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
