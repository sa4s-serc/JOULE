import time
import logging
from typing import Dict, Optional

try:
    from codecarbon import EmissionsTracker
    CODECARBON_AVAILABLE = True
except ImportError:
    CODECARBON_AVAILABLE = False

logger = logging.getLogger(__name__)

class EnergyMonitor:
    def __init__(self, use_codecarbon: bool = True):
        self.use_codecarbon = use_codecarbon and CODECARBON_AVAILABLE
        self.tracker: Optional[EmissionsTracker] = None
        if self.use_codecarbon:
            try:
                # Initialize in offline mode to avoid network calls if possible, 
                # or just standard mode. Using standard for now but suppressing logs.
                self.tracker = EmissionsTracker(
                    log_level="error",
                    save_to_file=False,
                    measure_power_secs=0.1
                )
            except Exception as e:
                logger.warning(f"Failed to initialize CodeCarbon: {e}. Falling back to time-only.")
                self.use_codecarbon = False

    def start(self):
        self.start_time = time.perf_counter()
        if self.use_codecarbon and self.tracker:
            try:
                self.tracker.start()
            except Exception as e:
                logger.error(f"Error starting CodeCarbon: {e}")

    def stop(self) -> Dict[str, float]:
        end_time = time.perf_counter()
        duration = end_time - self.start_time
        
        metrics = {
            "duration_seconds": duration,
            "energy_joules": 0.0,
            "emissions_kg": 0.0
        }

        if self.use_codecarbon and self.tracker:
            try:
                emissions = self.tracker.stop()
                # CodeCarbon returns emissions in kg CO2eq. 
                # It also tracks energy consumed in kWh usually, but let's see what we get.
                # We can access the final emissions.
                # To get Joules, we might need to look at `final_emissions_data` if available
                # or just rely on emissions as the proxy.
                # However, for HEDGE, Joules is preferred.
                # CodeCarbon's `stop()` returns the emissions in kg.
                
                # Let's try to get energy if possible. 
                # The tracker object has `_total_energy` (kWh) after stop.
                energy_kwh = self.tracker.final_emissions_data.energy_consumed if self.tracker.final_emissions_data else 0.0
                metrics["energy_joules"] = energy_kwh * 3.6e6 # Convert kWh to Joules
                metrics["emissions_kg"] = emissions
            except Exception as e:
                logger.error(f"Error stopping CodeCarbon: {e}")
        
        return metrics
