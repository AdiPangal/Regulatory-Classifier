"""PII detection module using Presidio and regex patterns."""
import re
import warnings
import logging
from typing import List, Dict, Optional
from presidio_analyzer import AnalyzerEngine, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
import phonenumbers
from phonenumbers import carrier, geocoder, timezone

# Suppress Presidio warnings about unsupported languages
# These warnings occur when Presidio tries to load language-specific recognizers
# that aren't supported by the current NLP engine configuration
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message='.*Recognizer not added to registry.*')
warnings.filterwarnings('ignore', message='.*language is not supported.*')
logging.getLogger('presidio-analyzer').setLevel(logging.ERROR)
logging.getLogger('presidio_analyzer').setLevel(logging.ERROR)


class PIIDetector:
    """Detects PII using Presidio and regex patterns."""
    
    def __init__(self):
        """Initialize PII detector with Presidio and custom patterns."""
        # Initialize Presidio analyzer with English-only configuration
        try:
            # Configure to only use English recognizers
            # This prevents warnings about unsupported languages
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            
            # Create configuration that only supports English
            nlp_configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }
            
            try:
                provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
                nlp_engine = provider.create_engine()
                # Initialize analyzer with only English language support
                self.analyzer = AnalyzerEngine(
                    nlp_engine=nlp_engine,
                    supported_languages=["en"]
                )
            except Exception:
                # Fallback: initialize with English-only support
                self.analyzer = AnalyzerEngine(supported_languages=["en"])
        except Exception:
            # Final fallback: default analyzer with English-only
            try:
                self.analyzer = AnalyzerEngine(supported_languages=["en"])
            except Exception:
                # If that fails, use default but suppress warnings
                self.analyzer = AnalyzerEngine()
        
        # Add custom patterns
        self._add_custom_patterns()
        
        # Regex patterns for additional detection
        self.regex_patterns = {
            "SSN": [
                r'\b\d{3}-\d{2}-\d{4}\b',  # 123-45-6789
                r'\b\d{3}\s\d{2}\s\d{4}\b',  # 123 45 6789
                r'\b\d{9}\b'  # 123456789 (if context suggests SSN)
            ],
            "CreditCard": [
                r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # 16 digits
                r'\b\d{4}[\s-]?\d{6}[\s-]?\d{5}\b'  # Amex format
            ],
            "Email": [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ],
            "IPAddress": [
                r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            ]
        }
    
    def _add_custom_patterns(self):
        """Add custom pattern recognizers to Presidio."""
        try:
            # SSN pattern - use Pattern class for newer Presidio versions
            from presidio_analyzer import Pattern
            
            ssn_pattern = PatternRecognizer(
                supported_entity="SSN",
                patterns=[
                    Pattern(
                        name="ssn",
                        regex=r"\b\d{3}-\d{2}-\d{4}\b",
                        score=0.9
                    )
                ]
            )
            
            # Credit card pattern
            credit_card_pattern = PatternRecognizer(
                supported_entity="CREDIT_CARD",
                patterns=[
                    Pattern(
                        name="credit_card",
                        regex=r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
                        score=0.8
                    )
                ]
            )
            
            # Add to analyzer
            self.analyzer.registry.add_recognizer(ssn_pattern)
            self.analyzer.registry.add_recognizer(credit_card_pattern)
        except (ImportError, TypeError, AttributeError):
            # Fallback: try dictionary format for older versions
            try:
                ssn_pattern = PatternRecognizer(
                    supported_entity="SSN",
                    patterns=[
                        {
                            "name": "ssn",
                            "regex": r"\b\d{3}-\d{2}-\d{4}\b",
                            "score": 0.9
                        }
                    ]
                )
                
                credit_card_pattern = PatternRecognizer(
                    supported_entity="CREDIT_CARD",
                    patterns=[
                        {
                            "name": "credit_card",
                            "regex": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
                            "score": 0.8
                        }
                    ]
                )
                
                self.analyzer.registry.add_recognizer(ssn_pattern)
                self.analyzer.registry.add_recognizer(credit_card_pattern)
            except Exception:
                # If custom patterns fail, just skip them - regex detection will still work
                pass
    
    def detect_with_presidio(self, text: str, language: str = "en") -> List[Dict]:
        """Detect PII using Presidio.
        
        Args:
            text: Text to analyze
            language: Language code (default: en)
            
        Returns:
            List of detected PII entities
        """
        results = self.analyzer.analyze(text=text, language=language)
        
        detections = []
        for result in results:
            detections.append({
                "type": result.entity_type,
                "text": text[result.start:result.end],
                "start": result.start,
                "end": result.end,
                "score": result.score,
                "method": "presidio"
            })
        
        return detections
    
    def detect_with_regex(self, text: str) -> List[Dict]:
        """Detect PII using regex patterns.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of detected PII entities
        """
        detections = []
        
        for pii_type, patterns in self.regex_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Avoid duplicates
                    if not any(
                        d["start"] == match.start() and d["end"] == match.end()
                        for d in detections
                    ):
                        detections.append({
                            "type": pii_type,
                            "text": match.group(),
                            "start": match.start(),
                            "end": match.end(),
                            "score": 0.85,  # Default confidence for regex
                            "method": "regex"
                        })
        
        return detections
    
    def detect_phone_numbers(self, text: str) -> List[Dict]:
        """Detect phone numbers using phonenumbers library.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of detected phone numbers
        """
        detections = []
        
        # Try to find phone numbers in various formats
        for match in phonenumbers.PhoneNumberMatcher(text, "US"):
            number = match.number
            formatted = phonenumbers.format_number(
                number, phonenumbers.PhoneNumberFormat.NATIONAL
            )
            
            detections.append({
                "type": "PHONE_NUMBER",
                "text": formatted,
                "start": match.start,
                "end": match.end,
                "score": 0.9,
                "method": "phonenumbers"
            })
        
        return detections
    
    def detect_all(self, text: str, page_number: int) -> Dict:
        """Detect all PII in text using all methods.
        
        Args:
            text: Text to analyze
            page_number: Page number for citation
            
        Returns:
            Dictionary with all detected PII
        """
        # Combine all detection methods
        all_detections = []
        
        # Presidio detection
        presidio_results = self.detect_with_presidio(text)
        all_detections.extend(presidio_results)
        
        # Regex detection
        regex_results = self.detect_with_regex(text)
        all_detections.extend(regex_results)
        
        # Phone number detection
        phone_results = self.detect_phone_numbers(text)
        all_detections.extend(phone_results)
        
        # Remove duplicates (same position)
        unique_detections = []
        seen_positions = set()
        
        for detection in all_detections:
            pos_key = (detection["start"], detection["end"])
            if pos_key not in seen_positions:
                seen_positions.add(pos_key)
                unique_detections.append(detection)
        
        return {
            "page": page_number,
            "matches": unique_detections,
            "count": len(unique_detections)
        }
    
    def detect_sensitive_keywords(self, text: str, page_number: int) -> Dict:
        """Detect sensitive keywords (defense, financial, etc.).
        
        Args:
            text: Text to analyze
            page_number: Page number for citation
            
        Returns:
            Dictionary with detected keywords
        """
        # Define sensitive keyword categories
        # Note: These keywords indicate Confidential content, not Highly Sensitive
        # Highly Sensitive is reserved for documents with actual financial/identity PII
        sensitive_keywords = {
            "DEFENSE": [
                "stealth fighter", "military equipment", "classified",
                "top secret", "defense contract", "weapon system",
                "radar system", "missile", "aircraft design", "part number",
                "serial number", "technical specification"
            ],
            "FINANCIAL": [
                "account number", "routing number", "bank account",
                "wire transfer", "swift code", "tax id"
            ],
            "PROPRIETARY": [
                # Removed "proprietary", "nda" - too common in marketing materials
                "trade secret", "confidential information",
                "intellectual property",
                "schematic", "design specification", "technical drawing"
            ],
            "INTERNAL": [
                "internal memo", "internal communication", "internal document",
                "operational manual", "flight operations manual", "operations manual",
                "internal template", "internal sample",
                "research proposal", "proposal with comments", "internal review",
                "for internal use only", "not for public distribution"
                # Removed "confidential" - too generic, removed "template", "sample" - too common
            ]
        }
        
        detected_keywords = []
        text_lower = text.lower()
        
        for category, keywords in sensitive_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    # Find all occurrences
                    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                    for match in pattern.finditer(text):
                        detected_keywords.append({
                            "type": category,
                            "keyword": keyword,
                            "text": match.group(),
                            "start": match.start(),
                            "end": match.end(),
                            "score": 0.8
                        })
        
        return {
            "page": page_number,
            "matches": detected_keywords,
            "count": len(detected_keywords)
        }

