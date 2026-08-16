#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# pyHexCombinator v1.1
# Copyright (c) 2026 Suess Labs / Xeno Innovations, Inc.
# All rights reserved.
# Distributed under the terms of the MIT License

"""Combine two Intel HEX files into one output file.

The bootloader records are written first, then the main application records.
Input EOF records are removed and a single EOF record is written at the end.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Union


EOF_RECORD = ":00000001FF"
EOF_RECORD_TYPE = 0x01
START_LINEAR_ADDRESS_RECORD_TYPE = 0x05
VALID_RECORD_TYPES = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05}
PathLike = Union[str, Path]


class HexFileError(ValueError):
  """Raised when an input file is not valid Intel HEX."""


def _location(source: str, line_number: Optional[int]) -> str:
  if line_number is None:
    return source
  return f"{source} line {line_number}"


def parse_hex_record(line: str, source: str = "HEX record", line_number: Optional[int] = None) -> int:
  """Validate one Intel HEX record and return its record type."""
  where = _location(source, line_number)

  if not line.startswith(":"):
    raise HexFileError(f"{where}: record must start with ':'.")

  payload = line[1:]
  if len(payload) < 10 or len(payload) % 2 != 0:
    raise HexFileError(f"{where}: record length is invalid.")

  try:
    record_bytes = bytes.fromhex(payload)
  except ValueError as exc:
    raise HexFileError(f"{where}: record contains non-hexadecimal characters.") from exc

  if len(record_bytes) < 5:
    raise HexFileError(f"{where}: record is too short.")

  byte_count = record_bytes[0]
  address = (record_bytes[1] << 8) | record_bytes[2]
  record_type = record_bytes[3]
  data = record_bytes[4:-1]

  if len(data) != byte_count:
    raise HexFileError(
      f"{where}: byte count says {byte_count}, but record contains {len(data)} data bytes."
    )

  if (sum(record_bytes) & 0xFF) != 0:
    raise HexFileError(f"{where}: checksum is invalid.")

  if record_type not in VALID_RECORD_TYPES:
    raise HexFileError(f"{where}: unsupported record type 0x{record_type:02X}.")

  if record_type == EOF_RECORD_TYPE and (byte_count != 0 or address != 0):
    raise HexFileError(f"{where}: EOF record must have byte count 00 and address 0000.")

  return record_type


def _read_hex_body(path: Path, label: str) -> List[str]:
  if path.suffix.lower() != ".hex":
    raise HexFileError(f"{label} must have a .hex extension: {path}")

  records: List[str] = []
  saw_eof = False

  try:
    with path.open("r", encoding="utf-8-sig") as hex_file:
      for line_number, raw_line in enumerate(hex_file, start=1):
        line = raw_line.strip()
        if not line:
          continue

        if saw_eof:
          raise HexFileError(f"{label} has data after its EOF record at line {line_number}.")

        record_type = parse_hex_record(line, label, line_number)
        if record_type == EOF_RECORD_TYPE:
          saw_eof = True
        elif record_type == START_LINEAR_ADDRESS_RECORD_TYPE:
          # Ignore Start Linear Address records when combining files.
          continue
        else:
          records.append(line.upper())

  except FileNotFoundError as exc:
    raise HexFileError(f"{label} file was not found: {path}") from exc
  except UnicodeDecodeError as exc:
    raise HexFileError(f"{label} is not a readable text HEX file: {path}") from exc

  if not saw_eof:
    raise HexFileError(f"{label} is missing the EOF record {EOF_RECORD}.")

  return records


def default_output_path(bootloader_path: PathLike) -> Path:
  """Return the default Combined.hex path beside the bootloader file."""
  return Path(bootloader_path).expanduser().resolve().parent / "Combined.hex"


def combine_hex_files(
  bootloader_path: PathLike,
  mainapp_path: PathLike,
  output_path: Optional[PathLike] = None,
) -> Path:
  """Combine bootloader and main application HEX files into Combined.hex."""
  bootloader = Path(bootloader_path).expanduser().resolve()
  mainapp = Path(mainapp_path).expanduser().resolve()
  output = Path(output_path).expanduser().resolve() if output_path else default_output_path(bootloader)

  if output == bootloader or output == mainapp:
    raise HexFileError("Output path must be different from both input files.")

  bootloader_records = _read_hex_body(bootloader, "Bootloader")
  mainapp_records = _read_hex_body(mainapp, "MainApp")
  combined_records = bootloader_records + mainapp_records + [EOF_RECORD]

  output.parent.mkdir(parents=True, exist_ok=True)
  with output.open("w", encoding="ascii", newline="\n") as combined_file:
    for record in combined_records:
      combined_file.write(f"{record}\n")

  return output


def _build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Combine Bootloader.hex and MainApp.hex into Combined.hex.")
  parser.add_argument("bootloader", help="Path to the bootloader Intel HEX file.")
  parser.add_argument("mainapp", help="Path to the main application Intel HEX file.")
  parser.add_argument(
    "-o",
    "--output",
    help="Output path. Defaults to Combined.hex in the bootloader file's folder.",
  )
  return parser


def main(argv: Optional[List[str]] = None) -> int:
  parser = _build_parser()
  args = parser.parse_args(argv)

  try:
    output = combine_hex_files(args.bootloader, args.mainapp, args.output)
  except (HexFileError, OSError) as exc:
    print(f"Error: {exc}", file=sys.stderr)
    return 1

  print(f"Combined HEX written to: {output}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
