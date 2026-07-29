from src.validator.syntax_validator import SyntaxValidator
from src.validator.semantic_validator import SemanticValidator
from src.validator.permission_validator import PermissionValidator
from src.validator.safety_validator import SafetyValidator


class SQLValidator:

    def __init__(self):

        self.syntax = SyntaxValidator()

        self.semantic = SemanticValidator()

        self.permission = PermissionValidator()

        self.safety = SafetyValidator()

    def validate(self, query: str):

        validators = [

            self.syntax,

            self.semantic,

            self.permission,

            self.safety

        ]

        for validator in validators:

            result = validator.validate(query)

            if not result.valid:
                return result

        return result