# search_markdown.py — Markdown file search support
from __future__ import annotations
from typing import Callable, List, Any, Optional
import os
import re

Normalizer = Callable[[str], str]
Evaluator = Callable[..., List[dict]]

__all__ = ["search_in_markdown_file"]

def search_in_markdown_file(
    filepath: str,
    parser: Any,
    context_size: int,
    normalize: Optional[Normalizer] = None,
    evaluate_text: Optional[Evaluator] = None,
) -> List[dict]:
    """
    Lê ficheiros Markdown (.md) e aplica a avaliação.
    
    Extrai texto de:
    - Headers (# ## ###)
    - Parágrafos
    - Listas (bulleted e numbered)
    - Code blocks (opcionalmente)
    - Tables
    
    Args:
        filepath: Caminho para o ficheiro .md
        parser: BooleanSearchParser instance
        context_size: Tamanho da janela de contexto
        normalize: Função de normalização (opcional)
        evaluate_text: Função de avaliação (obrigatória)
        
    Returns:
        Lista de dicts com resultados
    """
    if evaluate_text is None:
        raise ValueError("evaluate_text callable é obrigatório.")
    normalize = normalize or (lambda s: s)
    
    try:
        # Tentar múltiplos encodings
        for enc in ("utf-8", "utf-8-sig", "utf-16", "latin-1", "cp1252"):
            try:
                with open(filepath, "r", encoding=enc) as f:
                    raw = f.read()
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"Error reading {filepath}: {e}")
                return []
        else:
            print(f"Could not decode {filepath} with any encoding")
            return []
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []
    
    # Parse Markdown (simples, sem dependências pesadas)
    # Extrai texto preservando estrutura básica
    results: List[dict] = []
    
    # Dividir em blocos (linhas vazias separam blocos)
    blocks = []
    current_block = []
    
    for line in raw.split('\n'):
        line_stripped = line.strip()
        
        # Linha vazia = fim de bloco
        if not line_stripped:
            if current_block:
                blocks.append('\n'.join(current_block))
                current_block = []
            continue
        
        # Headers (# ## ###)
        if line_stripped.startswith('#'):
            if current_block:
                blocks.append('\n'.join(current_block))
                current_block = []
            # Remover # e espaços
            header_text = line_stripped.lstrip('#').strip()
            if header_text:
                blocks.append(header_text)
            continue
        
        # Code blocks (ignorar por padrão, mas pode ser opcional)
        if line_stripped.startswith('```') or line_stripped.startswith('~~~'):
            if current_block:
                blocks.append('\n'.join(current_block))
                current_block = []
            # Pular até o fim do code block
            continue
        
        # List items (- * + ou números)
        if (line_stripped.startswith('- ') or 
            line_stripped.startswith('* ') or 
            line_stripped.startswith('+ ') or
            (len(line_stripped) > 2 and line_stripped[0].isdigit() and line_stripped[1] in ('.', ')'))):
            if current_block:
                blocks.append('\n'.join(current_block))
                current_block = []
            # Remover marcador de lista
            list_text = re.sub(r'^[-*+]\s+', '', line_stripped)
            list_text = re.sub(r'^\d+[.)]\s+', '', list_text)
            if list_text:
                blocks.append(list_text)
            continue
        
        # Tabelas (linhas com |)
        if '|' in line_stripped and line_stripped.count('|') >= 2:
            if current_block:
                blocks.append('\n'.join(current_block))
                current_block = []
            # Extrair células da tabela
            cells = [cell.strip() for cell in line_stripped.split('|') if cell.strip()]
            # Ignorar separadores de tabela (---)
            if not all(c.replace('-', '').replace(':', '').strip() == '' for c in cells):
                table_text = ' | '.join(cells)
                blocks.append(table_text)
            continue
        
        # Texto normal
        current_block.append(line)
    
    # Adicionar último bloco
    if current_block:
        blocks.append('\n'.join(current_block))
    
    # Avaliar cada bloco
    for idx, block in enumerate(blocks, start=1):
        if not block.strip():
            continue
        
        try:
            text = normalize(block)
            if text:
                hits = evaluate_text(
                    text, filepath, parser, context_size,
                    location=idx,
                    location_type="block"
                )
                if hits:
                    results.extend(hits)
        except Exception as e:
            print(f"Markdown evaluate error ({filepath}, block {idx}): {e}")
            continue
    
    return results
