"""A minimal performance test for OSDU ${SAMPLE_TITLE}."""

from osdu_perf import BaseService


class ${CLASS_NAME}(BaseService):
    """Performance test for the OSDU ${SAMPLE_TITLE} API."""

    def provide_explicit_token(self) -> str:
        return ""

    def prehook(self, headers=None, partition=None, host=None) -> None:
        pass

    def execute(self, headers=None, partition=None, host=None) -> None:
        # Example: a GET against a sample endpoint.
        self.client.get(
            "${SAMPLE_ENDPOINT}",
            name="${SAMPLE_NAME}",
            headers=headers,
        )

    def posthook(self, headers=None, partition=None, host=None) -> None:
        pass
