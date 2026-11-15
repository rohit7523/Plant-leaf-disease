
import os
import json
import logging
import sys
import re
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class DiseaseAnalysisResult:
    disease_detected: bool
    disease_name: Optional[str]
    disease_type: str
    severity: str
    confidence: float

    symptoms: List[str] = field(default_factory=list)
    possible_causes: List[str] = field(default_factory=list)
    treatment: List[str] = field(default_factory=list)
    prevention: List[str] = field(default_factory=list)

    analysis_timestamp: str = field(
        default_factory=lambda: datetime.now().astimezone().isoformat()
    )

    disease_name_hi: Optional[str] = None
    disease_type_hi: str = "अज्ञात"
    severity_hi: str = "अज्ञात"

    symptoms_hi: List[str] = field(default_factory=list)
    possible_causes_hi: List[str] = field(default_factory=list)
    treatment_hi: List[str] = field(default_factory=list)
    prevention_hi: List[str] = field(default_factory=list)

    # Exact field names expected by the Streamlit frontend
    hindi_explanation: str = ""
    hindi_symptoms: List[str] = field(default_factory=list)
    hindi_causes: List[str] = field(default_factory=list)
    hindi_treatment: List[str] = field(default_factory=list)
    hindi_prevention: List[str] = field(default_factory=list)


class LeafDiseaseDetector:

    MODEL_NAME = os.getenv("MODEL_NAME", "qwen/qwen3.8-27b")
    DEFAULT_TEMPERATURE = 0.3
    DEFAULT_MAX_TOKENS = 1800

    def __init__(self, api_key: Optional[str] = None):

        load_dotenv()

        self.api_key = api_key or os.environ.get("GROQ_API_KEY")

        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY not found in environment variables"
            )

        self.client = Groq(api_key=self.api_key)

        logger.info("Leaf Disease Detector initialized")

    def create_analysis_prompt(self) -> str:

        return """
You are an expert agricultural plant-health assistant.

Carefully inspect the uploaded image.

FIRST:
Determine whether the image clearly contains a real plant leaf.

Do not invent diseases or symptoms.
Only report visual findings supported by the image.

Return ONLY one valid JSON object.
Do not include Markdown or text outside JSON.

IMPORTANT LANGUAGE REQUIREMENT:
Every diagnosis MUST contain both English and Hindi.
Hindi must be natural, understandable Hindi written in Devanagari script.
Never leave Hindi fields empty.
Do not write Hindi using English/Roman letters.

Use this exact JSON structure:

{
  "disease_detected": true,
  "disease_name": "English disease name",
  "disease_name_hi": "हिंदी में रोग का नाम",
  "disease_type": "fungal",
  "disease_type_hi": "फफूंद जनित",
  "severity": "moderate",
  "severity_hi": "मध्यम",
  "confidence": 85,

  "symptoms": [
    "Brown circular spots on the leaf"
  ],
  "symptoms_hi": [
    "पत्तियों पर भूरे रंग के गोल धब्बे दिखाई देना।"
  ],

  "possible_causes": [
    "Fungal infection",
    "Excess moisture"
  ],
  "possible_causes_hi": [
    "फंगल संक्रमण।",
    "पत्तियों पर अधिक नमी।"
  ],

  "treatment": [
    "Remove infected leaves.",
    "Avoid overhead watering."
  ],
  "treatment_hi": [
    "संक्रमित पत्तियों को हटाकर नष्ट कर दें।",
    "पत्तियों पर ऊपर से पानी डालने से बचें।"
  ],

  "prevention": [
    "Maintain proper air circulation."
  ],
  "prevention_hi": [
    "पौधों के बीच उचित हवा का आवागमन बनाए रखें।"
  ],

  "hindi_explanation": "पत्तियों पर दिखाई देने वाले लक्षण फंगल संक्रमण की संभावना दर्शाते हैं।"
}

RULES:

1. Return all fields shown in the JSON structure.

2. English and Hindi list items must correspond to each other.
   Keep the same number of items in both languages.

3. Hindi must always use Devanagari script.

4. Explain the disease in hindi_explanation using 2-4
   understandable Hindi sentences.

5. Do not leave Hindi explanation, symptoms, causes,
   treatment or prevention empty when relevant.

6. If the leaf appears healthy:
   - disease_detected = false
   - disease_type = "healthy"
   - severity = "none"
   - Explain in both languages that no clear disease symptoms
     are visible.

7. If the image is not a plant leaf:
   - disease_detected = false
   - disease_type = "invalid_image"
   - severity = "none"
   - Explain in English and Hindi that a clear leaf image is required.

8. If the image is unclear:
   - disease_type = "uncertain"
   - Use a low confidence score.
   - Do not invent a diagnosis.

9. Provide practical and cautious treatment recommendations.
   Recommend consulting a local agriculture expert for
   severe or spreading infections.

10. Confidence must be a number between 0 and 100.
"""

    @staticmethod
    def _as_list(value):
        if value is None:
            return []

        if isinstance(value, list):
            return [str(item) for item in value if item is not None]

        if isinstance(value, str) and value.strip():
            return [value.strip()]

        return []

    def analyze_leaf_image_base64(
        self,
        base64_image: str,
        temperature: float = None,
        max_tokens: int = None
    ) -> Dict:

        try:
            logger.info("Starting leaf image analysis")

            if not isinstance(base64_image, str) or not base64_image:
                raise ValueError("base64_image must be a non-empty string")

            if base64_image.startswith("data:"):
                base64_image = base64_image.split(",", 1)[1]

            temperature = (
                self.DEFAULT_TEMPERATURE
                if temperature is None else temperature
            )

            max_tokens = (
                self.DEFAULT_MAX_TOKENS
                if max_tokens is None else max_tokens
            )

            completion = self.client.chat.completions.create(
                model=self.MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self.create_analysis_prompt()
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": (
                                        "data:image/jpeg;base64,"
                                        + base64_image
                                    )
                                }
                            }
                        ]
                    }
                ],
                temperature=temperature,
                max_completion_tokens=max_tokens,
                top_p=1,
                stream=False,
                response_format={"type": "json_object"}
            )

            response_content = (
                completion.choices[0].message.content
            )

            result = self._parse_response(response_content)

            logger.info("Leaf image analysis completed successfully")

            return result.__dict__

        except Exception as error:
            logger.exception("Leaf analysis failed: %s", error)
            raise

    def _build_result(self, data: Dict) -> DiseaseAnalysisResult:

        # Accept both old and new Hindi field names
        symptoms_hi = self._as_list(
            data.get("symptoms_hi") or data.get("hindi_symptoms")
        )

        causes_hi = self._as_list(
            data.get("possible_causes_hi")
            or data.get("hindi_causes")
            or data.get("hindi_possible_causes")
        )

        treatment_hi = self._as_list(
            data.get("treatment_hi") or data.get("hindi_treatment")
        )

        prevention_hi = self._as_list(
            data.get("prevention_hi") or data.get("hindi_prevention")
        )

        symptoms = self._as_list(data.get("symptoms"))
        causes = self._as_list(data.get("possible_causes"))
        treatment = self._as_list(data.get("treatment"))
        prevention = self._as_list(data.get("prevention"))

        hindi_explanation = (
            data.get("hindi_explanation")
            or data.get("explanation_hi")
            or data.get("disease_explanation_hi")
            or ""
        )

        if not hindi_explanation and data.get("disease_name_hi"):
            hindi_explanation = (
                f"पहचानी गई स्थिति: {data['disease_name_hi']}। "
                f"गंभीरता: {data.get('severity_hi', 'अज्ञात')}।"
            )

        try:
            confidence = float(data.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = max(0.0, min(100.0, confidence))

        return DiseaseAnalysisResult(
            disease_detected=bool(data.get("disease_detected", False)),
            disease_name=data.get("disease_name"),
            disease_type=data.get("disease_type", "unknown"),
            severity=data.get("severity", "unknown"),
            confidence=confidence,

            symptoms=symptoms,
            possible_causes=causes,
            treatment=treatment,
            prevention=prevention,

            disease_name_hi=(
                data.get("disease_name_hi")
                or data.get("disease_name")
            ),
            disease_type_hi=data.get("disease_type_hi", "अज्ञात"),
            severity_hi=data.get("severity_hi", "अज्ञात"),

            symptoms_hi=symptoms_hi,
            possible_causes_hi=causes_hi,
            treatment_hi=treatment_hi,
            prevention_hi=prevention_hi,

            # Frontend-compatible aliases
            hindi_explanation=str(hindi_explanation),
            hindi_symptoms=symptoms_hi,
            hindi_causes=causes_hi,
            hindi_treatment=treatment_hi,
            hindi_prevention=prevention_hi
        )

    def _parse_response(
        self,
        response_content: str
    ) -> DiseaseAnalysisResult:

        if not response_content:
            raise ValueError("AI returned an empty response")

        cleaned_response = response_content.strip()

        if cleaned_response.startswith("```"):
            cleaned_response = re.sub(
                r"^```(?:json)?\s*",
                "",
                cleaned_response
            )
            cleaned_response = re.sub(
                r"\s*```$",
                "",
                cleaned_response
            )

        try:
            disease_data = json.loads(cleaned_response)

        except json.JSONDecodeError:
            logger.warning("Trying to extract JSON from AI response")

            json_match = re.search(
                r"\{.*\}",
                cleaned_response,
                re.DOTALL
            )

            if not json_match:
                raise ValueError("AI response did not contain valid JSON")

            disease_data = json.loads(json_match.group())

        if not isinstance(disease_data, dict):
            raise ValueError("AI response must be a JSON object")

        logger.info("AI JSON response parsed successfully")

        return self._build_result(disease_data)


def main():

    try:
        detector = LeafDiseaseDetector()

        print(
            "Leaf Disease Detector initialized successfully!"
        )

        print("Model:", detector.MODEL_NAME)

    except Exception as error:
        print("Error:", str(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
