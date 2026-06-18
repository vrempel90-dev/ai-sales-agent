from dataclasses import dataclass


@dataclass
class GrowthRuntimeState:
    autopilot_override: bool | None = None
    last_action: str = "ещё не запускался"
    last_error: str = ""
    posts_added: int = 0
    last_report_date: str = ""

    def enabled(self, configured: bool) -> bool:
        return configured if self.autopilot_override is None else self.autopilot_override


growth_runtime = GrowthRuntimeState()
