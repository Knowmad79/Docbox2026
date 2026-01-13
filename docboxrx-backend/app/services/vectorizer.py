import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any

from pydantic import BaseModel
from cerebras.cloud.sdk import Cerebras
import asyncio


class EmailInput(BaseModel):
    subject: str
    body: str
    sender: str
    message_id: str
    grant_id: str


class VectorizerService:
    def __init__(self) -> None:
        self.api_key = os.getenv("CEREBRAS_API_KEY")
        if not self.api_key:
            print("WARNING: CEREBRAS_API_KEY not found. Vectorizer will fail.")

        self.client = Cerebras(api_key=self.api_key)
        self.model = "llama3.3-70b"

    def _build_prompt(self, email: EmailInput) -> str:
        return f"""
You are the \"State Vector Engine\" for a high-volume medical practice.
Your job is to analyze incoming raw email data and convert it into a deterministic business object.

INPUT EMAIL:
Subject: {email.subject}
Sender: {email.sender}
Body: {email.body[:2000]}

INSTRUCTIONS:
Analyze the email and output a valid JSON object containing exactly these fields:

1. \"intent_label\" (String): Choose ONE: \"CLINICAL\", \"BILLING\", \"ADMIN\", \"SCHEDULING\", \"VENDOR\", \"SPAM\".
2. \"risk_score\" (Float): 0.0 (No risk) to 1.0 (High risk/Malpractice/Revenue Loss).
   - > 0.8: Urgent clinical distress, legal threat, missed surgery.
   - > 0.5: Billing denial, patient complaint.
   - < 0.2: Routine admin.
3. \"context_blob\" (Object): Extract entities if present (patient_name, mrn, dollar_amount, insurance_provider). Return empty object {{}} if none.
4. \"suggested_deadline_hours\" (Integer): Fibonacci sequence (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144).
5. \"summary\" (String): A 10-word Twitter-style summary.

OUTPUT JSON ONLY. NO MARKDOWN.
"""

    def _call_llm(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            messages=[{"role": "system", "content": prompt}],
            model=self.model,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    async def vectorize_email(self, email: EmailInput) -> Dict[str, Any]:
        prompt = self._build_prompt(email)

        try:
            content = await asyncio.to_thread(self._call_llm, prompt)
            vector_data = json.loads(content)

            hours = vector_data.get("suggested_deadline_hours", 24)
            deadline = datetime.now() + timedelta(hours=hours)

            return {
                "nylas_message_id": email.message_id,
                "grant_id": email.grant_id,
                "intent_label": vector_data.get("intent_label", "ADMIN"),
                "risk_score": vector_data.get("risk_score", 0.0),
                "context_blob": vector_data.get("context_blob", {}),
                "summary": vector_data.get("summary", "No summary generated"),
                "deadline_at": deadline,
                "lifecycle_state": "NEW",
            }

        except Exception as e:
            print(f"ERROR: Vectorization Failed: {e}")
            return {
                "nylas_message_id": email.message_id,
                "grant_id": email.grant_id,
                "intent_label": "ADMIN",
                "risk_score": 0.0,
                "context_blob": {"error": str(e)},
                "summary": "AI Processing Failed",
                "deadline_at": datetime.now() + timedelta(hours=24),
                "lifecycle_state": "NEW",
            }


vectorizer = VectorizerService()
