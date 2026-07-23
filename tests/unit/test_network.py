import pytest
from unittest.mock import MagicMock, patch
import paramiko
import subprocess

from rtranscoder.network import TranscoderNode

#===============================================
# open_connection and close_connection tests
#===============================================

@patch("paramiko.SSHClient")
def test_open_connection_success(mock_ssh_class, transcoder_node):

    mock_client = MagicMock()
    mock_ssh_class.return_value = mock_client

    result = transcoder_node.open_connection(max_retries=3)

    assert result is True
    mock_client.connect.assert_called_once_with(
            hostname="192.168.0.1",
            username="worker_user",
            key_filename="/path/to/key",
            timeout=10
        )

@patch("time.sleep", return_value=None)  
@patch("paramiko.SSHClient")
def test_open_connection_retry_and_succeed(mock_ssh_class, mock_sleep, transcoder_node):
    mock_client = MagicMock()
    mock_client.connect.side_effect = [
        paramiko.SSHException("Connection refused"),
        None,
    ]
    mock_ssh_class.return_value = mock_client

    result = transcoder_node.open_connection(max_retries=3)

    assert result is True
    assert mock_client.connect.call_count == 2


@patch("time.sleep", return_value=None)
@patch("paramiko.SSHClient")
def test_open_connection_failure_max_retries(mock_ssh_class, mock_sleep, transcoder_node):
    mock_client = MagicMock()
    mock_client.connect.side_effect = paramiko.SSHException("Network unreachable")
    mock_ssh_class.return_value = mock_client

    result = transcoder_node.open_connection(max_retries=3)

    assert result is False
    assert mock_client.connect.call_count == 3


def test_close_connection(transcoder_node):
    mock_client = MagicMock()
    transcoder_node.client = mock_client

    transcoder_node.close_connection()

    mock_client.close.assert_called_once()
    assert transcoder_node.client is None



#===============================================
# execute_command() tests
#===============================================

def test_execute_command_raises_without_connection(transcoder_node):
    with pytest.raises(ConnectionError, match="No SSH connection active"):
        transcoder_node.execute_command("ls")


def test_execute_command_success(transcoder_node):
    mock_client = MagicMock()

    mock_stdout = MagicMock()
    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_stdout.read.return_value = b"Output OK"

    mock_stderr = MagicMock()
    mock_stderr.read.return_value = b""

    mock_client.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
    transcoder_node.client = mock_client

    status, out, err = transcoder_node.execute_command("uname -a")

    assert status == 0
    assert out == "Output OK"
    assert err == ""
    mock_client.exec_command.assert_called_once_with("uname -a")


#===============================================
# execute_command() tests
#===============================================

@patch("subprocess.run")
def test_media_transfer_local_success(mock_subprocess, transcoder_node):
    transcoder_node.host_id = "127.0.0.1"
    mock_subprocess.return_value = MagicMock(stdout="sent 100 bytes")

    result = transcoder_node.media_transfer(
        source="/local/video.mkv", destination="/local/dest/video.mkv"
    )

    assert result is True

    mock_subprocess.assert_called_once_with(
        ["rsync", "-ahv", "--progress", "/local/video.mkv", "/local/dest/video.mkv"],
        capture_output=True,
        check=True,
        text=True,
    )


@patch("subprocess.run")
def test_media_transfer_remote_success(mock_subprocess, transcoder_node):
    transcoder_node.host_id = "192.168.1.100"
    transcoder_node.host_user = "worker_user"
    mock_subprocess.return_value = MagicMock(stdout="sent 100 bytes")

    result = transcoder_node.media_transfer(
        source="/local/video.mkv", destination="/remote/video.mkv"
    )

    assert result is True

    mock_subprocess.assert_called_once_with(
        [
            "rsync",
            "-a",
            "-e",
            "ssh",
            "/local/video.mkv",
            "worker_user@192.168.1.100:/remote/video.mkv",
        ],
        capture_output=True,
        check=True,
        text=True,
    )


@patch("subprocess.run")
def test_media_transfer_failure(mock_subprocess, transcoder_node):
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd="rsync", stderr="Permission denied"
    )

    result = transcoder_node.media_transfer(
        source="/local/video.mkv", destination="/remote/video.mkv"
    )

    assert result is False


#===============================================
# execute_command() tests
#===============================================

@patch.object(TranscoderNode, "execute_command")
def test_execute_remote_transcode_success(mock_execute_command, transcoder_node):
    mock_execute_command.return_value = (0, "frame= 1000 fps= 60", "")

    input_file = "/media/Movie with Espace.mkv"
    output_file = "/media/Movie with Espace.mp4"

    result = transcoder_node.execute_remote_transcode(input_file, output_file)

    assert result is True

    expected_command = (
        "nice -n 19 ffmpeg -y -i '/media/Movie with Espace.mkv' "
        "-map 0:v:0 -map 0:a "
        "-c:v libx264 -preset fast -crf 22 "
        "-c:a aac -b:a 192k "
        "'/media/Movie with Espace.mp4'"
    )
    mock_execute_command.assert_called_once_with(expected_command)


@patch.object(TranscoderNode, "execute_command")
def test_execute_remote_transcode_failure(mock_execute_command, transcoder_node):
    mock_execute_command.return_value = (
        1,
        "",
        "Error: Invalid data found when processing input\n",
    )

    input_file = "/media/corrupted.mkv"
    output_file = "/media/corrupted.mp4"

    result = transcoder_node.execute_remote_transcode(input_file, output_file)

    assert result is False

    mock_execute_command.assert_called_once()
