import os
from pathlib import Path
from typing import Callable, Optional

def remover_e_confirmar_arquivo_original(
        caminho_original: str | Path,
        caminho_redigido: str | Path,
        download_concluido: bool = True,
        callback_exibicao: Optional[Callable[[str], None]] = None,
) -> dict:

    exibir = callback_exibicao if callback_exibicao else print
    original = Path(caminho_original)
    redigido = Path(caminho_redigido)

    if not download_concluido:
        mensagem = (
            "[AVISO] O download do arquivo redigido não foi concluído."
            "O download do arquivo redigido ainda não foi concluído"
        )
        exibir(mensagem)
        return {"status": "pendente", "removido": False, "mensagem": mensagem}

    if not redigido.exists() or redigido.stat().st_size == 0:
        mensagem = (
            "[ERRO] O arquivo redigido não existe ou está vazio."
            "Por segurança, o arquivo original não foi removido."
        )
        exibir(mensagem)
        return {"status": "erro", "removido": False, "mensagem": mensagem}

    if original.resolve() == redigido.resolve():
        mensagem = (
            "[ERRO] O caminho do arquivo original e do redigido são idênticos. "
            "Remoção abortada por segurança."
        )
        exibir(mensagem)
        return {"status": "erro", "removido": False, "mensagem": mensagem}

    if not original.exists():
        mensagem = (
            f"[INFO] O arquivo original '{original.name}' já não se encontra no diretório."
        )
        exibir(mensagem)
        return {"status": "sucesso", "removido": True, "mensagem": mensagem}

    try:
        os.remove(original)
        mensagem = (
            f"[SUCESSO] O arquivo original '{original.name}' adicionado para censura "
            "foi removido com sucesso após a censura e o download do arquivo redigido."
        )
        exibir(mensagem)
        return {"status": "sucesso", "removido": True, "mensagem": mensagem}
    except PermissionError:
        mensagem = (
            f"[ERRO] Permissão negada ao tentar remover o arquivo original '{original.name}'. "
            "Verifique se ele não está aberto em outro programa."
        )
        exibir(mensagem)
        return {"status": "erro", "removido": False, "mensagem": mensagem}
    except OSError as erro:
        mensagem = (
            f"[ERRO] Falha ao remover o arquivo original '{original.name}': {erro}"
        )
        exibir(mensagem)
        return {"status": "erro", "removido": False, "mensagem": mensagem}