from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class SegmentSpec:
    name: str

@dataclass(frozen=True)
class SegmentEvent:
    next_segment: SegmentSpec

    @staticmethod
    def split_to(segment_name: str) -> "SegmentEvent":
        return SegmentEvent(next_segment=SegmentSpec(name=segment_name))

@dataclass
class SegmentMeta:
    index: int
    name: str
    file_path: Path

class SplitEngine:
    def __init__(
        self,
        input_file: Path,
        output_dir: Path,
        header_lines: Optional[list[str]] = None,
        encoding: str = "utf-8"
    ) -> None:
        self.input_file = os.path.splitext(os.path.basename(Path(input_file)))[0]
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.encoding = encoding
        self.header_lines = header_lines

        self._segment_index = 0
        self._current_segment = SegmentSpec(name="initial")
        self._current_meta: Optional[SegmentMeta] = None
        self._current_fp = None
        self._segments: list[SegmentMeta] = []
        self._open_new_segment(self._current_segment)
    
    def _open_new_segment(self, segment: SegmentSpec) -> None:
        self._segment_index += 1
        path = self.output_dir / f"{self._segment_index:04d}_{segment.name}_{self.input_file}.asc"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._current_fp = path.open("w", encoding=self.encoding, newline="")
        if self._segment_index > 1 and self.header_lines is not None:
            for line in self.header_lines:
                self._current_fp.write(line)

        self._current_segment = segment
        self._current_meta = SegmentMeta(
            index=self._segment_index,
            name=segment.name,
            file_path=path
        )
        self._segments.append(self._current_meta)
    
    def _close_current_segment(self) -> None:
        if self._current_fp is not None:
            self._current_fp.close()
            self._current_fp = None
    
    def write_line(self, line: str) -> None:
        if self._current_fp is None:
            raise RuntimeError("No open segment to write to")
        self._current_fp.write(line)
    
    def run(self, line: str, event: Optional[SegmentEvent]) -> None:
        if event is None:
            self.write_line(line)
            return

        self._close_current_segment()
        self._open_new_segment(
            event.next_segment
        )
        self.write_line(line)
        return

    def close(self) -> None:
        self._close_current_segment()

class SplitChecker(ABC):
    @abstractmethod
    def check_line(self, line: str) -> Optional[SegmentEvent]:
        raise NotImplementedError()
    
class FileSplitter:
    def __init__(self, checker: SplitChecker, engine: SplitEngine) -> None:
        self.checker = checker
        self.engine = engine
    
    def split_file(self, file_path: Path) -> list[SegmentMeta]:
        file_path = Path(file_path)
        try:
            with file_path.open("r", encoding=self.engine.encoding) as f:
                for line in f:
                    event = self.checker.check_line(line)
                    self.engine.run(line, event)
        finally:
            self.engine.close()
        return self.engine._segments