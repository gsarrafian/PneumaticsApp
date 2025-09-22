
try:
    import RPi.GPIO as GPIO
    _ON_PI = True
except Exception:
    GPIO = None
    _ON_PI = False

class GPIOController:
    def __init__(self, mode="BOARD"):
        self.mode = mode
        self._setup_done = False
        self.active = set()

    def _ensure_setup(self):
        if self._setup_done:
            return
        if _ON_PI:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BOARD if self.mode == "BOARD" else GPIO.BCM)
        self._setup_done = True

    def _ensure_pin(self, pin):
        self._ensure_setup()
        if _ON_PI and pin not in self.active:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            self.active.add(pin)

    def set(self, pin: int, high: bool):
        self._ensure_pin(pin)
        if _ON_PI:
            GPIO.output(pin, GPIO.HIGH if high else GPIO.LOW)

    def cleanup(self):
        if _ON_PI:
            GPIO.cleanup()