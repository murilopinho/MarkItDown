#!/usr/bin/env python3
"""
Conversor universal de documentos para Markdown — CLI
Lógica de conversão: converter_core.py
"""

import sys
import argparse
from pathlib import Path

from converter_core import convert_file, SUPPORTED_EXTENSIONS


def install_deps():
    import subprocess
    packages = ["html2text", "python-docx", "pdfminer.six", "pandas", "openpyxl"]
    cmd = [sys.executable, "-m", "pip", "install", "--quiet"]
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )
    if not in_venv:
        cmd.append("--user")
    subprocess.check_call(cmd + packages)


def main():
    parser = argparse.ArgumentParser(
        description="Converte documentos para Markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python convert_to_markdown_cli.py relatorio.pdf
  python convert_to_markdown_cli.py planilha.xlsx
  python convert_to_markdown_cli.py documento.docx -o saida.md
  python convert_to_markdown_cli.py pagina.html -o resultado.md
  python convert_to_markdown_cli.py dados.csv

Formatos suportados:
  HTML (.html, .htm)  |  Word (.docx)  |  PDF (.pdf)
  CSV (.csv)          |  Excel (.xlsx, .xls)  |  Texto (.txt, .rst, .log)
        """,
    )
    parser.add_argument("input", nargs="?", help="Arquivo de entrada")
    parser.add_argument(
        "-o", "--output",
        help="Arquivo de saída (padrão: mesmo nome com .md)",
        default=None,
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Instalar dependências automaticamente",
    )

    args = parser.parse_args()

    if args.install:
        print("Instalando dependências...")
        install_deps()
        print("Dependências instaladas!\n")
        if not args.input:
            return

    if not args.input:
        parser.print_help()
        sys.exit(1)

    path = Path(args.input)
    if not path.exists():
        print(f"\nErro: arquivo não encontrado: {args.input}")
        sys.exit(1)

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        print(f"\nErro: formato '{ext}' não suportado.")
        print(f"Formatos aceitos: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        sys.exit(1)

    print(f"Convertendo: {path.name}")
    try:
        _markdown, output = convert_file(args.input, args.output)
        print(f"Salvo em: {output}")
    except ImportError as e:
        missing = str(e).split("'")[1] if "'" in str(e) else str(e)
        print(f"\nDependência faltando: {missing}")
        print("Execute com --install primeiro:")
        print(f"  python convert_to_markdown_cli.py --install {args.input}")
        sys.exit(1)
    except (FileNotFoundError, ValueError) as e:
        print(f"\nErro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
