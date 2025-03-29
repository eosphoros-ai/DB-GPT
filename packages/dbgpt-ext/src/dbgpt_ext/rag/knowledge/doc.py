import struct
from typing import Any, Dict, List, Optional, Union

import olefile

from dbgpt.core import Document
from dbgpt.rag.knowledge.base import (
    ChunkStrategy,
    DocumentType,
    Knowledge,
    KnowledgeType,
)


class Word97DocParser:
    """Parser for Microsoft Word 97-2003 (.doc) binary files.

    This module implements a parser for the legacy Word 97-2003 binary format (.doc),
    based on the official Microsoft [MS-DOC] specification.

    Specification Reference:
        [MS-DOC]: Word (.doc) Binary File Format
        https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/ccd7b486-7881-484c-a137-51170af7cc22

    Example:
        >>> from doc import Word97DocParser
        >>> with Word97DocParser("example.doc") as parser:
        ...     paragraphs = parser.extract_text_by_paragraphs()
        ...     for i, para in enumerate(paragraphs, 1):
        ...         print(f"\nParagraph {i}:")
        ...         print(para)
    """

    # Mapping of special ANSI characters to Unicode
    ANSI_TO_UNICODE = {
        0x82: 0x201A,
        0x83: 0x0192,
        0x84: 0x201E,
        0x85: 0x2026,
        0x86: 0x2020,
        0x87: 0x2021,
        0x88: 0x02C6,
        0x89: 0x2030,
        0x8A: 0x0160,
        0x8B: 0x2039,
        0x8C: 0x0152,
        0x91: 0x2018,
        0x92: 0x2019,
        0x93: 0x201C,
        0x94: 0x201D,
        0x95: 0x2022,
        0x96: 0x2013,
        0x97: 0x2014,
        0x98: 0x02DC,
        0x99: 0x2122,
        0x9A: 0x0161,
        0x9B: 0x203A,
        0x9C: 0x0153,
        0x9F: 0x0178,
    }

    # Mapping of nFib values to cbRgFcLcb sizes
    FIB_VERSIONS = {
        0x00C1: 0x005D,  # Word 97
        0x00D9: 0x006C,  # Word 2000
        0x0101: 0x0088,  # Word 2002
        0x010C: 0x00A4,  # Word 2003
        0x0112: 0x00B7,  # Word 2007
    }

    def __init__(self, doc_path):
        """Initialize with path to Word document"""
        self.doc_path = doc_path
        self.ole = None
        self.word_doc_stream = None
        self.table_stream = None
        self.fib_info = None
        self.plc_pcd = None

    def __enter__(self):
        """Context manager entry"""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def open(self):
        """Open the OLE file and required streams"""
        self.ole = olefile.OleFileIO(self.doc_path)

        if not self.ole.exists("WordDocument"):
            raise ValueError("WordDocument stream not found")

        self.word_doc_stream = self.ole.openstream("WordDocument")

        # Determine table stream name
        table_stream_name = "0Table" if self.ole.exists("0Table") else "1Table"
        self.table_stream = self.ole.openstream(table_stream_name)

    def close(self):
        """Close all open resources"""
        if self.ole:
            self.ole.close()
        self.ole = None
        self.word_doc_stream = None
        self.table_stream = None

    def read_fib(self):
        """Read the File Information Block (FIB) from the WordDocument stream (2.5)"""
        # Read FibBase (32 bytes)
        fib_base = self.word_doc_stream.read(32)

        # Unpack nFib (offset 2, size 2 bytes)
        nFib = struct.unpack("<H", fib_base[2:4])[0]
        if nFib not in self.FIB_VERSIONS:
            raise ValueError(f"Unsupported nFib version: 0x{nFib:04X}")

        # Skip csw (2 bytes at offset 32)
        self.word_doc_stream.read(2)

        # Skip FibRgW97 (28 bytes) and cslw (2 bytes)
        self.word_doc_stream.read(28 + 2)

        # Read FibRgLw97 (88 bytes)
        fib_rg_lw = self.word_doc_stream.read(88)
        ccpText = struct.unpack("<I", fib_rg_lw[12:16])[0]  # Total character count

        # Read cbRgFcLcb (2 bytes)
        cb_rg_fc_lcb = struct.unpack("<H", self.word_doc_stream.read(2))[0]

        # Read FibRgFcLcbBlob (variable size)
        fib_rg_fc_lcb_blob = self.word_doc_stream.read(cb_rg_fc_lcb * 8)

        # Skip cswNew (2 bytes) and FibRgCswNew (variable size)
        csw_new = struct.unpack("<H", self.word_doc_stream.read(2))[0]
        if csw_new > 0:
            self.word_doc_stream.read(csw_new * 2)

        # Extract fcClx and lcbClx from FibRgFcLcb97
        fc_clx = struct.unpack("<I", fib_rg_fc_lcb_blob[0x108:0x10C])[0]
        lcb_clx = struct.unpack("<I", fib_rg_fc_lcb_blob[0x10C:0x110])[0]
        fc_plcf_bte_papx = struct.unpack("<I", fib_rg_fc_lcb_blob[0x68:0x6C])[0]
        lcb_plcf_bte_papx = struct.unpack("<I", fib_rg_fc_lcb_blob[0x6C:0x70])[0]
        self.fib_info = {
            "nFib": nFib,
            "fcClx": fc_clx,
            "lcbClx": lcb_clx,
            "ccpText": ccpText,
            "fcPlcfBtePapx": fc_plcf_bte_papx,
            "lcbPlcfBtePapx": lcb_plcf_bte_papx,
        }
        return self.fib_info

    def read_clx(self, fc_clx, lcb_clx):
        """Read the CLX structure from the Table stream"""
        self.table_stream.seek(fc_clx)
        clx_data = self.table_stream.read(lcb_clx)

        # For simplicity, we assume the data starts with Pcdt (0x02)
        if clx_data[0] != 0x02:
            raise ValueError("Expected Pcdt structure not found in CLX data")

        return clx_data

    def parse_plc_pcd(self, pcdt_data):
        """Parse the PLC structure containing PCDs(2.9.177)"""
        # Get the size of PlcPcd structure
        lcb = struct.unpack("<I", pcdt_data[1:5])[0]
        plc_pcd_bytes = pcdt_data[5 : 5 + lcb]

        # Calculate number of PCDs: n = (lcb - 4) // 12
        n = (lcb - 4) // 12

        # Parse aCP array (n+1 CPs, each 4 bytes)
        aCP = [
            struct.unpack("<I", plc_pcd_bytes[i * 4 : (i + 1) * 4])[0]
            for i in range(n + 1)
        ]

        # Parse aPcd array (n PCDs, each 8 bytes)
        aPcd = []
        for i in range(n):
            start = (n + 1) * 4 + i * 8
            pcd_bytes = plc_pcd_bytes[start : start + 8]

            # Extract fc (bytes 2-6) and compression flag
            fc_bytes = pcd_bytes[2:6]
            fc = int.from_bytes(fc_bytes, byteorder="little", signed=False)
            fcompressed = (fc >> 1) & 0x1

            aPcd.append(
                {
                    "fc": fc,
                    "start": aCP[i],
                    "end": aCP[i + 1],
                    "f_compressed": fcompressed,
                }
            )
        self.plc_pcd = {"aCP": aCP, "aPcd": aPcd}
        return self.plc_pcd

    def _find_pcd_index(self, cp):
        """Find the index of the PCD containing the given character position"""
        aCP = self.plc_pcd["aCP"]
        for i in range(len(aCP) - 1):
            if aCP[i] <= cp < aCP[i + 1]:
                return i
        return None

    def get_paragraph_boundaries(self, cp):
        """Find paragraph boundaries for a given character position (2.4.2)"""
        if not self.fib_info or not self.plc_pcd:
            raise RuntimeError("Must read FIB and PLC/PCD first")

        # Find the PCD containing this cp
        i = self._find_pcd_index(cp)
        if i is None:
            return None

        pcd = self.plc_pcd["aPcd"][i]
        start_cp = self._find_paragraph_start(cp, i, pcd)
        end_cp = self._find_paragraph_end(cp, i, pcd)

        return (start_cp, end_cp)

    def _find_paragraph_start(self, cp, i, pcd):
        """Find the start of the paragraph containing cp (algorithm 2.4.2)"""
        # Step 3: Calculate fc and fc_pcd
        fc_pcd = pcd["fc"]
        # Let fcPcd be Pcd.fc.fc. Let fc be fcPcd + 2(cp – PlcPcd.aCp[i]).
        # If Pcd.fc.fCompressed is one, set fc to fc / 2, and set fcPcd to fcPcd/2.
        fc = fc_pcd + 2 * (cp - self.plc_pcd["aCP"][i])
        if pcd["f_compressed"]:
            fc = fc // 2
            fc_pcd = fc_pcd // 2

        # Step 4: Read PlcBtePapx
        self.table_stream.seek(self.fib_info["fcPlcfBtePapx"])
        plcf_bte_papx_data = self.table_stream.read(self.fib_info["lcbPlcfBtePapx"])
        a_fc, a_pn = self._parse_plcf_bte_papx(plcf_bte_papx_data)

        # Handle case where a_fc is empty
        if not a_fc:
            return None

        fc_last = a_fc[-1]

        # Step 4 continued: Check fcLast
        if fc_last <= fc:
            if fc_last < fc_pcd:
                # Step 8: Check if at beginning of document
                if self.plc_pcd["aCP"][i] == 0:
                    return 0
                # Step 9: Recurse with previous cp
                return self._find_paragraph_start(
                    self.plc_pcd["aCP"][i], i - 1, self.plc_pcd["aPcd"][i - 1]
                )
            # Adjust fc and fc_last if needed
            fc = fc_last
            if pcd["f_compressed"]:
                fc_last = fc_last // 2
            fc_first = fc_last
        else:
            # Step 5: Find largest j where a_fc[j] <= fc
            j = self._find_largest_index_le(a_fc, fc)
            if j is None:
                return None  # Invalid cp

            # Read PapxFkp
            papx_fkp = self._read_papx_fkp(a_pn[j])
            # print(f"papx_fkp:{papx_fkp}, j:{j}")
            if not papx_fkp or not papx_fkp.get("rgfc"):
                return None  # Invalid data

            # Step 6: Find largest k where rgfc[k] <= fc
            k = self._find_largest_index_le(papx_fkp["rgfc"], fc)
            if k is None:
                return None  # Invalid cp

            # Check if cp is outside document range
            if papx_fkp["rgfc"][-1] <= fc:
                return None

            fc_first = papx_fkp["rgfc"][k]

        # Step 7: Calculate paragraph start
        if fc_first > fc_pcd:
            dfc = fc_first - fc_pcd
            if not pcd["f_compressed"]:
                dfc = dfc // 2
            return self.plc_pcd["aCP"][i] + dfc

        # Step 8: Check if at beginning of document
        if self.plc_pcd["aCP"][i] == 0:
            return 0

        # Step 9: Recurse with previous cp
        return self._find_paragraph_start(
            self.plc_pcd["aCP"][i], i - 1, self.plc_pcd["aPcd"][i - 1]
        )

    def _find_paragraph_end(self, cp, i, pcd):
        """Find the end of the paragraph containing cp (algorithm 2.4.2)"""
        fc_pcd = pcd["fc"]
        fc = fc_pcd + 2 * (cp - self.plc_pcd["aCP"][i])
        fc_mac = fc_pcd + 2 * (self.plc_pcd["aCP"][i + 1] - self.plc_pcd["aCP"][i])

        if pcd["f_compressed"]:
            fc = fc // 2
            fc_pcd = fc_pcd // 2
            fc_mac = fc_mac // 2

        # Read PlcBtePapx
        self.table_stream.seek(self.fib_info["fcPlcfBtePapx"])
        plcf_bte_papx_data = self.table_stream.read(self.fib_info["lcbPlcfBtePapx"])
        a_fc, a_pn = self._parse_plcf_bte_papx(plcf_bte_papx_data)

        # Find largest j where a_fc[j] <= fc
        j = self._find_largest_index_le(a_fc, fc)
        if j is None or (a_fc and fc >= a_fc[-1]):
            return self._find_paragraph_end(
                self.plc_pcd["aCP"][i + 1], i + 1, self.plc_pcd["aPcd"][i + 1]
            )

        # Read PapxFkp
        papx_fkp = self._read_papx_fkp(a_pn[j])
        if not papx_fkp:
            return None

        # Find largest k where rgfc[k] <= fc
        k = self._find_largest_index_le(papx_fkp["rgfc"], fc)
        if k is None or (papx_fkp["rgfc"] and fc >= papx_fkp["rgfc"][-1]):
            return None

        fc_lim = papx_fkp["rgfc"][k + 1] if k + 1 < len(papx_fkp["rgfc"]) else fc_mac

        if fc_lim <= fc_mac:
            dfc = fc_lim - fc_pcd
            if not pcd["f_compressed"]:
                dfc = dfc // 2
            return self.plc_pcd["aCP"][i] + dfc - 1

        return self._find_paragraph_end(
            self.plc_pcd["aCP"][i + 1], i + 1, self.plc_pcd["aPcd"][i + 1]
        )

    def _parse_plcf_bte_papx(self, data):
        """Parse PlcBtePapx structure (2.8.6)

        Args:
            data: Raw bytes of PlcBtePapx structure.

        Returns:
            (a_fc, a_pn): Tuple of two lists:
                - a_fc: List of unsigned 4-byte integers (FC offsets).
                - a_pn: List of unsigned 4-byte integers (PnFkpPapx entries).

        Raises:
            ValueError: If data is malformed or aFC is not sorted/unique.
        """
        if len(data) < 12:  # Minimum: 8 (aFC[0..1]) + 4 (aPnBtePapx[0])
            return [], []

        # Calculate number of aPnBtePapx entries (n)
        n = (len(data) - 4) // 8
        if (2 * n + 1) * 4 != len(data):
            raise ValueError("Invalid PlcBtePapx size")

        a_fc = []
        a_pn = []

        # Parse aFC (n+1 entries, each 4 bytes)
        for i in range(n + 1):
            offset = i * 4
            fc = struct.unpack("<I", data[offset : offset + 4])[0]
            a_fc.append(fc)

        # Parse aPnBtePapx (n entries, each 4 bytes, starting after last aFC)
        pn_offset = (n + 1) * 4
        for i in range(n):
            offset = pn_offset + i * 4
            pn = struct.unpack("<I", data[offset : offset + 4])[0]
            a_pn.append(pn)

        # Validate aFC is strictly increasing (sorted and unique)
        for i in range(len(a_fc) - 1):
            if a_fc[i] >= a_fc[i + 1]:
                raise ValueError("aFC must be strictly increasing")

        return a_fc, a_pn

    def _read_papx_fkp(self, pn):
        """Read PapxFkp structure from WordDocument stream.

        Args:
            pn: Page number (PnFkpPapx), offset = pn * 512.

        Returns:
            Dict with keys:
                - "rgfc": List of FC offsets (4-byte unsigned integers).
                - "rgbx": List of BxPap (1-byte integers).
                - "papx_in_fkp": List of PapxInFkp raw bytes.

        Raises:
            ValueError: If FKP data is invalid.
        """
        offset = pn * 512
        self.word_doc_stream.seek(offset)
        fkp_data = self.word_doc_stream.read(512)

        if len(fkp_data) != 512:
            raise ValueError("FKP size must be 512 bytes")

        cpara = fkp_data[511]  # Number of paragraphs (1 ≤ cpara ≤ 0x1D)
        if not 1 <= cpara <= 0x1D:
            raise ValueError(f"Invalid cpara: {cpara} (must be 1 ≤ cpara ≤ 29)")

        # Parse rgfc (cpara + 1 entries, each 4 bytes)
        rgfc = []
        for i in range(cpara + 1):
            fc_offset = i * 4
            fc = struct.unpack("<I", fkp_data[fc_offset : fc_offset + 4])[0]
            rgfc.append(fc)

        # Parse rgbx (cpara entries, each 1 byte)
        rgbx_start = (cpara + 1) * 4
        rgbx = list(fkp_data[rgbx_start : rgbx_start + cpara])

        # Parse PapxInFkp (variable size, located after rgbx)
        papx_in_fkp_start = rgbx_start + cpara
        papx_in_fkp_end = 511  # cpara is the last byte
        papx_in_fkp = fkp_data[papx_in_fkp_start:papx_in_fkp_end]

        return {
            "rgfc": rgfc,
            "rgbx": rgbx,
            "papx_in_fkp": papx_in_fkp,
        }

    def _find_largest_index_le(self, array, value):
        """Find largest index where array[index] <= value"""
        for i in reversed(range(len(array))):
            if array[i] <= value:
                return i
        return None

    def extract_text_by_paragraphs(self):
        """Extract text organized by paragraphs"""
        self.word_doc_stream.seek(0)
        self.table_stream.seek(0)
        self.read_fib()
        clx_data = self.read_clx(self.fib_info["fcClx"], self.fib_info["lcbClx"])
        self.parse_plc_pcd(clx_data)

        paragraphs = []
        current_cp = 0
        total_chars = self.fib_info["ccpText"]

        while current_cp < total_chars:
            boundaries = self.get_paragraph_boundaries(current_cp)
            if not boundaries:
                break

            start, end = boundaries
            if start > end:
                break

            paragraph_text = self._extract_text_range(start, end)
            paragraphs.append(paragraph_text)
            current_cp = end + 1

        return paragraphs

    def _extract_text_range(self, start_cp, end_cp):
        """Extract text between two character positions"""
        text_chars = []
        i = self._find_pcd_index(start_cp)

        while i is not None and start_cp <= end_cp:
            pcd = self.plc_pcd["aPcd"][i]
            pcd_start = self.plc_pcd["aCP"][i]
            pcd_end = self.plc_pcd["aCP"][i + 1]

            # Determine range within this PCD
            range_start = max(start_cp, pcd_start)
            range_end = min(end_cp, pcd_end - 1)

            if range_start > range_end:
                i += 1
                continue

            fc = pcd["fc"]
            compressed = pcd["f_compressed"]

            for cp in range(range_start, range_end + 1):
                if compressed:
                    offset = fc + (cp - pcd_start)
                    self.word_doc_stream.seek(offset)
                    char_byte = self.word_doc_stream.read(1)
                    char_code = char_byte[0]
                    char = chr(self.ANSI_TO_UNICODE.get(char_code, char_code))
                else:
                    offset = fc + 2 * (cp - pcd_start)
                    self.word_doc_stream.seek(offset)
                    char_bytes = self.word_doc_stream.read(2)
                    char = char_bytes.decode("utf-16-le")

                text_chars.append(char)

            start_cp = range_end + 1
            i += 1

        return "".join(text_chars)

    def extract_text(self):
        """Main method to extract text from the document"""
        self.word_doc_stream.seek(0)
        self.table_stream.seek(0)
        fib_info = self.read_fib()
        clx_data = self.read_clx(fib_info["fcClx"], fib_info["lcbClx"])
        pcd_array = self.parse_plc_pcd(clx_data)

        full_text = []
        for pcd in pcd_array["aPcd"]:
            start_cp, end_cp = pcd["start"], pcd["end"]
            char_count = end_cp - start_cp

            if char_count == 0:
                continue

            fc = pcd["fc"]
            compressed = pcd["f_compressed"]
            text_chars = []

            for cp in range(start_cp, end_cp):
                offset = (
                    fc + (cp - start_cp) if compressed else fc + 2 * (cp - start_cp)
                )
                self.word_doc_stream.seek(offset)

                if compressed:
                    char_byte = self.word_doc_stream.read(1)
                    char_code = char_byte[0]
                    char = chr(self.ANSI_TO_UNICODE.get(char_code, char_code))
                else:
                    char_bytes = self.word_doc_stream.read(2)
                    # decode char
                    char = char_bytes.decode("utf-16-le")
                text_chars.append(char)
            full_text.append("".join(text_chars))

        return "".join(full_text)


class Word97DocKnowledge(Knowledge):
    """Microsoft Word 97-2003 (.doc)."""

    def __init__(
        self,
        file_path: Optional[str] = None,
        knowledge_type: Any = KnowledgeType.DOCUMENT,
        encoding: Optional[str] = "utf-16-le",
        loader: Optional[Any] = None,
        metadata: Optional[Dict[str, Union[str, List[str]]]] = None,
        **kwargs: Any,
    ) -> None:
        """Create  Microsoft Word 97-2003 (.doc) Knowledge with Knowledge arguments.

        Args:
            file_path(str,  optional): file path
            knowledge_type(KnowledgeType, optional): knowledge type
            encoding(str, optional): .doc encoding
            loader(Any, optional): loader
        """
        super().__init__(
            path=file_path,
            knowledge_type=knowledge_type,
            data_loader=loader,
            metadata=metadata,
            **kwargs,
        )
        self._encoding = encoding

    def _load(self) -> List[Document]:
        """Load doc document from loader."""
        if self._loader:
            documents = self._loader.load()
        else:
            docs = []
            content = []
            with Word97DocParser(self._path) as parser:
                paragraphs = parser.extract_text_by_paragraphs()
                for i, para in enumerate(paragraphs):
                    content.append(para)

            metadata = {"source": self._path}
            if self._metadata:
                metadata.update(self._metadata)  # type: ignore
            docs.append(Document(content="\n".join(content), metadata=metadata))
            return docs
        return [Document.langchain2doc(lc_document) for lc_document in documents]

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        """Return support chunk strategy."""
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_PARAGRAPH,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    @classmethod
    def default_chunk_strategy(cls) -> ChunkStrategy:
        """Return default chunk strategy."""
        return ChunkStrategy.CHUNK_BY_SIZE

    @classmethod
    def type(cls) -> KnowledgeType:
        """Return knowledge type."""
        return KnowledgeType.DOCUMENT

    @classmethod
    def document_type(cls) -> DocumentType:
        """Return document type."""
        return DocumentType.DOC
