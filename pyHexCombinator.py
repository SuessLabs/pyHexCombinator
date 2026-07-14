"""Combine two Intel HEX files into one output file.

The bootloader records are written first, then the main application records.
Input EOF records are removed and a single EOF record is written at the end.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union


EOF_RECORD = ":00000001FF"
EOF_RECORD_TYPE = 0x01
VALID_RECORD_TYPES = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05}
PathLike = Union[str, Path]


@dataclass(frozen=True)
class HexRecord:
    byte_count: int
    address: int
    record_type: int
    data: bytes


@dataclass(frozen=True)
class HexFileBody:
    records: List[str]
    memory_range: Optional[Tuple[int, int]]


class HexFileError(ValueError):
    """Raised when an input file is not valid Intel HEX."""


def _location(source: str, line_number: Optional[int]) -> str:
    if line_number is None:
        return source
    return f"{source} line {line_number}"


def parse_hex_record(line: str, source: str = "HEX record", line_number: Optional[int] = None) -> HexRecord:
    """Validate one Intel HEX record and return its decoded fields."""
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

    if record_type in {0x02, 0x04} and (byte_count != 2 or address != 0):
        raise HexFileError(f"{where}: extended address record is malformed.")

    if record_type in {0x03, 0x05} and (byte_count != 4 or address != 0):
        raise HexFileError(f"{where}: start address record is malformed.")

    return HexRecord(byte_count=byte_count, address=address, record_type=record_type, data=data)


def _read_hex_body(path: Path, label: str) -> HexFileBody:
    if path.suffix.lower() != ".hex":
        raise HexFileError(f"{label} must have a .hex extension: {path}")

    records: List[str] = []
    saw_eof = False
    address_base = 0
    range_start: Optional[int] = None
    range_end: Optional[int] = None

    try:
        with path.open("r", encoding="utf-8-sig") as hex_file:
            for line_number, raw_line in enumerate(hex_file, start=1):
                line = raw_line.strip()
                if not line:
                    continue

                if saw_eof:
                    raise HexFileError(f"{label} has data after its EOF record at line {line_number}.")

                record = parse_hex_record(line, label, line_number)
                if record.record_type == EOF_RECORD_TYPE:
                    saw_eof = True
                else:
                    records.append(line.upper())

                if record.record_type == 0x02:
                    address_base = int.from_bytes(record.data, byteorder="big") << 4
                elif record.record_type == 0x04:
                    address_base = int.from_bytes(record.data, byteorder="big") << 16
                elif record.record_type == 0x00 and record.byte_count > 0:
                    data_start = address_base + record.address
                    data_end = data_start + record.byte_count - 1
                    range_start = data_start if range_start is None else min(range_start, data_start)
                    range_end = data_end if range_end is None else max(range_end, data_end)
    except FileNotFoundError as exc:
        raise HexFileError(f"{label} file was not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise HexFileError(f"{label} is not a readable text HEX file: {path}") from exc

    if not saw_eof:
        raise HexFileError(f"{label} is missing the EOF record {EOF_RECORD}.")

    memory_range = None if range_start is None or range_end is None else (range_start, range_end)
    return HexFileBody(records=records, memory_range=memory_range)


def write_mem_range_file(mainapp_body: HexFileBody, output_path: Path) -> Path:
    """Write mem_range.txt using the MainApp's start address and address span."""
    if mainapp_body.memory_range is None:
        raise HexFileError("MainApp does not contain any data records.")

    start_address, end_address = mainapp_body.memory_range
    address_span = end_address - start_address
    mem_range_path = output_path.parent / "mem_range.txt"

    with mem_range_path.open("w", encoding="ascii", newline="\n") as mem_range_file:
        mem_range_file.write(f"#{start_address:08X}\n")
        mem_range_file.write(f"!{address_span:08X}\n")

    return mem_range_path


def default_output_path(bootloader_path: PathLike) -> Path:
    """Return the default Combined.hex path beside the bootloader file."""
    return Path(bootloader_path).expanduser().resolve().parent / "Combined.hex"


def combine_hex_files(
    bootloader_path: PathLike,
    mainapp_path: PathLike,
    output_path: Optional[PathLike] = None,
) -> Tuple[Path, Path]:
    """Combine bootloader and main application HEX files and write mem_range.txt."""
    bootloader = Path(bootloader_path).expanduser().resolve()
    mainapp = Path(mainapp_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve() if output_path else default_output_path(bootloader)

    if output == bootloader or output == mainapp:
        raise HexFileError("Output path must be different from both input files.")

    bootloader_body = _read_hex_body(bootloader, "Bootloader")
    mainapp_body = _read_hex_body(mainapp, "MainApp")
    combined_records = bootloader_body.records + mainapp_body.records + [EOF_RECORD]

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="ascii", newline="\n") as combined_file:
        for record in combined_records:
            combined_file.write(f"{record}\n")

    mem_range_path = write_mem_range_file(mainapp_body, output)
    return output, mem_range_path


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
        output, mem_range_path = combine_hex_files(args.bootloader, args.mainapp, args.output)
    except (HexFileError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Combined HEX written to: {output}")
    print(f"Memory range written to: {mem_range_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
