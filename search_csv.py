# search_csv.py — CSV file search support
from __future__ import annotations
from typing import Callable, List, Any, Optional
import os
import csv

Normalizer = Callable[[str], str]
Evaluator = Callable[..., List[dict]]

__all__ = ["search_in_csv_file"]

def _detect_csv_delimiter(filepath: str, sample_size: int = 8192) -> str:
    """
    Detecta o delimitador CSV (vírgula, ponto-e-vírgula, tab, pipe).
    
    Args:
        filepath: Caminho para o ficheiro CSV
        sample_size: Tamanho da amostra para análise
        
    Returns:
        Delimitador detectado (default: ',')
    """
    delimiters = [',', ';', '\t', '|']
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            sample = f.read(sample_size)
        
        # Contar ocorrências de cada delimitador
        counts = {}
        for delim in delimiters:
            counts[delim] = sample.count(delim)
        
        # Retornar o delimitador mais frequente
        if max(counts.values()) > 0:
            return max(counts, key=counts.get)
        
        return ','
    except Exception:
        return ','

def search_in_csv_file(
    filepath: str,
    parser: Any,
    context_size: int,
    normalize: Optional[Normalizer] = None,
    evaluate_text: Optional[Evaluator] = None,
) -> List[dict]:
    """
    Lê ficheiros CSV e aplica a avaliação.
    
    Extrai texto de cada célula e cada linha completa.
    Suporta múltiplos delimitadores (vírgula, ponto-e-vírgula, tab, pipe).
    
    Args:
        filepath: Caminho para o ficheiro CSV
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
    
    results: List[dict] = []
    
    # Detectar delimitador
    delimiter = _detect_csv_delimiter(filepath)
    
    # Tentar múltiplos encodings
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            with open(filepath, 'r', encoding=enc, newline='', errors='replace') as f:
                # Tentar ler como CSV
                try:
                    reader = csv.reader(f, delimiter=delimiter, quotechar='"')
                    
                    for row_idx, row in enumerate(reader, start=1):
                        # Avaliar cada célula individualmente
                        for col_idx, cell_value in enumerate(row, start=1):
                            if not cell_value or not cell_value.strip():
                                continue
                            
                            try:
                                text = normalize(cell_value.strip())
                                if text:
                                    # Location: row, col
                                    location_str = f"R{row_idx}:C{col_idx}"
                                    hits = evaluate_text(
                                        text, filepath, parser, context_size,
                                        location=location_str,
                                        location_type="cell"
                                    )
                                    if hits:
                                        results.extend(hits)
                            except Exception as e:
                                print(f"CSV evaluate error ({filepath}, R{row_idx}C{col_idx}): {e}")
                                continue
                        
                        # Também avaliar a linha completa (para contexto)
                        row_text = ' | '.join([cell.strip() for cell in row if cell.strip()])
                        if row_text:
                            try:
                                text = normalize(row_text)
                                if text:
                                    location_str = f"R{row_idx}"
                                    hits = evaluate_text(
                                        text, filepath, parser, context_size,
                                        location=location_str,
                                        location_type="row"
                                    )
                                    if hits:
                                        results.extend(hits)
                            except Exception as e:
                                print(f"CSV evaluate error ({filepath}, row {row_idx}): {e}")
                                continue
                    
                    # Sucesso - sair do loop de encoding
                    break
                    
                except csv.Error:
                    # Se falhar como CSV, tentar como texto simples
                    f.seek(0)
                    raw = f.read()
                    text = normalize(raw)
                    if text:
                        hits = evaluate_text(
                            text, filepath, parser, context_size,
                            location=1,
                            location_type="file"
                        )
                        if hits:
                            results.extend(hits)
                    break
                    
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"CSV Error {filepath}: {e}")
            return []
    
    return results
