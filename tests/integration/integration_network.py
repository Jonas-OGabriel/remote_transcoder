from rtranscoder.network import TranscoderNode
from pathlib import Path

if __name__ == "__main__":
    print("Hello World")

    test_host_id = "127.0.0.1"
    test_host_user = "joao"
    test_start_directory = Path("/home/joao/Documentos/Projetos") / "Projeto 2 - Auto-Transcode" / "devel_resources/server_storage/video_teste.mkv"
    test_destiny_directory = Path("/home/joao/Documentos/Projetos") / "Projeto 2 - Auto-Transcode" / "devel_resources/worker_storage"

    test_brute_file = f"{str(test_destiny_directory)}/video_teste.mkv"
    test_converted_file = f"{str(test_destiny_directory)}/video_pronto.mp4"


    print(f"Criando objeto com as variaveis: {test_host_id}:{test_host_user}")

    test_transcoder = TranscoderNode(test_host_id,test_host_user)

    if test_transcoder.open_connection():
        _, test_stdout, test_stderr = test_transcoder.execute_command("echo 'Conexao Operacional'")
        print(f"[TESTE] Resposta do Host: {test_stdout.strip()}")
        print("Testando a transferencia de arquivo")
        test_transcoder.media_transfer(str(test_start_directory), str(test_destiny_directory))
        test_transcoder.execute_remote_transcode(test_brute_file, test_converted_file)
        test_transcoder.close_connection()
