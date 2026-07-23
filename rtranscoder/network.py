import logging
import paramiko
import time
import subprocess
import shlex

logger = logging.getLogger(__name__) #rtrancoder.network

class TranscoderNode:

    def __init__(self, host_id: str, host_user: str, key_path: str | None = None ) -> None:
        self.host_id = host_id
        self.host_user = host_user
        self.key_path = key_path
        self.client: paramiko.SSHClient | None = None

    def open_connection(self, max_retries: int = 3) -> bool:
        for attempt in range(1, max_retries + 1):
            try:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                logger.info(f"[SSH] Trying to connect with {self.host_user}@{self.host_id} (attempt [{attempt}/{max_retries}])")
                self.client.connect(
                        hostname=self.host_id,
                        username=self.host_user,
                        key_filename=self.key_path,
                        timeout=10
                        )
                logger.info("[SSH] Connection established successfully")
                return True
            except (paramiko.SSHException, TimeoutError) as e:
                logger.warning(f"[SSH] Failed attempt [{attempt}] to connect to host {self.host_id}: {e}")
                self.close_connection()

                if attempt < max_retries:
                    time.sleep(2)

            except Exception as e:
               logger.error(f"[SSH] Unexpected error when trying to connect to the host: {e}")
               self.close_connection()
               return False
               
        logger.error(f"[SSH] Not possible to connect to {self.host_id} after {max_retries} attempts")
        return False

    def close_connection(self) -> None:
        if self.client:
            try:
                self.client.close()
                logger.info(f"[SSH] Connection to host {self.host_id} closed")
            except Exception as e:
                logger.error(f"[SSH] Error while trying to close connection to host {self.host_id}: {e}")
            finally:
                self.client = None

    def execute_command(self, command: str) -> tuple[int, str, str]:
        if not self.client:
            logger.error("[CMD] Attempt to execute remote command without SSH connection")
            raise ConnectionError("No SSH connection active. call 'open_connection()' first")

        logger.debug(f"[CMD] Executing remote command at {self.host_id}: {command}")
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            out_str = stdout.read().decode('utf-8')
            err_str = stderr.read().decode('utf-8')

            if exit_status != 0:
                logger.warning(f"[CMD] Command '{command}' returned an error code: {exit_status} - Stderr: {err_str.strip()}")

            return exit_status, out_str, err_str 

        except Exception as e:
            logger.error(f"[CMD] Error while executing remote command '{command}': {e}")
            raise

    def media_transfer(self, source: str, destination: str) -> bool:
        if self.host_id in ["127.0.0.1", "localhost"]:
            cmd = ["rsync", "-ahv", "--progress", source, destination]#Remove this if...else check when applying and validating on server
        else:
            #using list[str] here to do not use the flag shell=True, because we could have files names with space on them. Python interpreter will handle this if we use the list
            destination_remote = f"{self.host_user}@{self.host_id}:{destination}"
            cmd = ["rsync", "-a", "-e", "ssh", source, destination_remote] #-a to indicate that we will use file on rsync, -e ssh to execute the next command on ssh

        logger.info(f"[RSYNC] Initiating transfer via Rsync: {source} -> {destination}")

        try:
            result = subprocess.run(cmd, capture_output=True,check=True, text=True)
            logger.debug(f"[RSYNC] Output: {result.stdout.strip()}")
            logger.info("[RSYNC] File transfer completed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"[RSYNC] Rsync failed. Code: {e.returncode} | Error: {e.stderr.strip()}")
            return False

    def execute_remote_transcode(self, input_file: str, output_file: str) -> bool:
        safe_input = shlex.quote(input_file)
        safe_output = shlex.quote(output_file)

        ffmpeg_cmd = (
                f"ffmpeg -y -i {safe_input} " # -y confirms the overwrite (if exists), -i {input} add the input of the command (file to transcode)
                f"-c:v libx264 -preset fast -crf 22 " #-c:v libx264 uses the h.264(AVC) codec for video, -preset fast uses the fast preset in the transcode, -crf 22 Constant Rate Factor at 22 (sweet spot in the middle)
                f"-c:a aac -b:a 192k " #-c:a aac uses the aac codec for audio, -b:a 192k bitrate audio at 192kbps
                f"{safe_output}" #output of the transcoded file
                )
        final_cmd = f"nice -n 19 {ffmpeg_cmd}"

        logger.info(f"[TCODE] Initiating remote transcoding in the worker for {input_file}.")
        exit_status, stdout, stderr = self.execute_command(final_cmd)
        
        if exit_status == 0: #mux
            logger.info(f"[TCODE] transcoding of the {input_file} file completed successfully.")
            return True
        else:    
            logger.error(f"[TCODE] Remote file transcoding error: {input_file} : {stderr.strip()}")
            return False

