import struct
import sys
from pathlib import Path
import logging
import binascii
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class SummaryFileTester:
    """Test reader for ResMed .000 summary files"""
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        # Adjusted based on C++ struct:
        # - 4 byte magic number
        # - 4 byte version
        # - 8 byte timestamp
        self.header_fmt = '<I I Q'  # magic, version, timestamp
        self.header_size = struct.calcsize(self.header_fmt)
        
    def _debug_bytes(self, data: bytes, label: str):
        """Hex dump of bytes for debugging"""
        hex_str = binascii.hexlify(data).decode('ascii')
        logging.debug(f"{label} bytes: {hex_str}")

    def test_read(self) -> bool:
        """Attempt to read file with full error checking"""
        try:
            if not self.filepath.exists():
                logging.error(f"File not found: {self.filepath}")
                return False
                
            file_size = self.filepath.stat().st_size
            logging.info(f"Testing {self.filepath.name} ({file_size} bytes)")
            
            if file_size < self.header_size:
                logging.error(f"File too small: {file_size} < {self.header_size}")
                return False
                
            with self.filepath.open('rb') as f:
                # Read and debug header
                header_data = f.read(self.header_size)
                self._debug_bytes(header_data, "Header")
                
                if len(header_data) != self.header_size:
                    logging.error("Failed to read complete header")
                    return False
                    
                try:
                    magic, version, timestamp = struct.unpack(self.header_fmt, header_data)
                except struct.error as e:
                    logging.error(f"Header unpack failed: {e}")
                    return False
                
                logging.info(f"Magic: 0x{magic:08X}, Version: {version}, Timestamp: {timestamp}")
                
                # Read remaining data as session records
                session_fmt = '<I I I I'  # Example: 4 int fields per session
                session_size = struct.calcsize(session_fmt)
                remaining = file_size - self.header_size
                
                if remaining % session_size != 0:
                    logging.warning(f"File size mismatch: {remaining} bytes remaining")
                
                num_sessions = remaining // session_size
                for i in range(num_sessions):
                    session_data = f.read(session_size)
                    self._debug_bytes(session_data, f"Session {i}")
                    try:
                        session = struct.unpack(session_fmt, session_data)
                        logging.info(f"Session {i}: {session}")
                    except struct.error as e:
                        logging.error(f"Session unpack failed: {e}")
                        return False
                    
            return True
            
        except Exception as e:
            logging.exception("Test failed with exception")
            return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_summary_reader.py <filepath> [filepath2 ...]")
        sys.exit(1)
        
    for filepath in sys.argv[1:]:
        test_file = Path(filepath)
        print(f"\nTesting {test_file}:")
        tester = SummaryFileTester(test_file)
        success = tester.test_read()
        print(f"Test {'succeeded' if success else 'failed'}")