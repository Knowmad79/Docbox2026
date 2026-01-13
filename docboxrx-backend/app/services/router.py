from typing import Dict, Any


class RoutingEngine:
    ROLES = {
        "CLINICAL": "medical_assistant",
        "BILLING": "billing_specialist",
        "ADMIN": "front_desk",
        "SCHEDULING": "front_desk",
        "VENDOR": "office_manager",
        "SPAM": "system_archive",
    }

    def route_vector(self, vector_data: Dict[str, Any]) -> Dict[str, Any]:
        intent = vector_data.get("intent_label")
        risk = vector_data.get("risk_score", 0.0)

        owner_role = self.ROLES.get(intent, "front_desk")

        if risk > 0.8:
            if intent == "CLINICAL":
                owner_role = "lead_doctor"
            elif intent == "BILLING":
                owner_role = "practice_manager"

        vector_data["current_owner_role"] = owner_role
        return vector_data


router = RoutingEngine()
