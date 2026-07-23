import pytest
from rtranscoder.network import TranscoderNode

@pytest.fixture
def transcoder_node():
    return TranscoderNode(
            host_id = "192.168.0.1",
            host_user = "worker_user",
            key_path = "/path/to/key"
        )
