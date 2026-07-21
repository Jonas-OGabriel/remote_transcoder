import paramiko
import time
import subprocess
import shlex

#To do
#1-Change print for logging
#2-Put everything in english
#3-Correct any grammar error

class TranscoderNode:

    def __init__(self, host_id: str, host_user: str, key_path: str | None = None ) -> None:
        self.host_id = host_id
        self.host_user = host_user
        self.key_path = key_path
        self.client = None

    def open_connection(self, max_retries: int = 3) -> bool:
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        for tentative in range(1, max_retries + 1):
            try:
                print(f"[SSH] Tentando se conectar: {self.host_user}@{self.host_id}. Tentative [{tentative}]")
                self.client.connect(
                        hostname=self.host_id,
                        username=self.host_user,
                        key_filename=self.key_path,
                        timeout=10
                        )
                print("[SSH] Conexao estabelecida com sucesso")
                return True
            except Exception as e:
                print(f"[SSH] Erro de conexao: {e}")
                if tentative < max_retries:
                    time.sleep(2)
        return False

    def close_connection(self) -> None:
        if self.client:
            self.client.close()
            print("[SSH] Conexao fechada")

    def execute_command(self, command: str) -> tuple[int, str, str]:
        if not self.client:
            raise ConnectionError("Nao ha conexao SSH ativa")
        stdin, stdout, stderr = self.client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        return exit_status, stdout.read().decode('utf-8'), stderr.read().decode('utf-8')

    def media_transfer(self, origin: str, destiny: str) -> bool:
        if self.host_id in ["127.0.0.1", "localhost"]:
            cmd = ["rsync", "-ahv", "--progress", origin, destiny] #Remove this if...else check when applying and validating on server
        else:
            #using list[str] here to do not use the flagshell=True, because we could have files nbames with space on them. Python interpreter will handle this if we use the list
            cmd = ["rsync", "-a", "-e", "ssh", origin, f"{self.host_user}@{self.host_id}:{destiny}"] #-a to indicate that we will use file on rsync, -e ssh to execute the next command on ssh

        print(f"[RSYNC] Iniciando a transferencia: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True, text=True)
            print("[RSYNC] Transferencia concluida com sucesso")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[RSYNC] Falha na transferencia do arquivo: {e}")
            return False

    def execute_remote_transcode(self, cmd_input: str, cmd_output: str) -> bool:
        ffmpeg_cmd = (
                f"ffmpeg -y -i {shlex.quote(cmd_input)} " # -y confirms the overwrite (if exists), -i {input} add the input of the command (file to transcode)
                f"-c:v libx264 -preset fast -crf 22 " #-c:v libx264 uses the h.264(AVC) codec foir video, -preset fast uses the fast preset in the transcode, -crf 22 Constant Rate Factor at 22 (sweet spot in the middle)
                f"-c:a aac -b:a 192k " #-c:a aac uses the aac codec for audio, -b:a 192k bitrate audio at 192kbps
                f"{shlex.quote(cmd_output)}" #output of the transcoded file
                )
        final_cmd = f"nice -n 19 {ffmpeg_cmd}"

        print("[TRANSCODE] Solicitando execucao do no worker...")
        exit_status, stdout, stderr = self.execute_command(final_cmd)
        
        if exit_status == 0: #"mux
            print("[TRANSCODE] Processamento concluido no no worker")
            return True
        else:    
            print(f"[TRANSCODE] Erro critico detectado: {stderr}")
            return False

        


