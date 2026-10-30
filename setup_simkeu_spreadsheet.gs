/**
 * SIMKEU Kecamatan Candisari 2027 — Google Apps Script Setup
 * 
 * Script ini akan membuat spreadsheet dengan semua worksheet yang diperlukan,
 * lengkap dengan header kolom sesuai spesifikasi aplikasi.
 * 
 * CARA PAKAINYA:
 * 1. Buka https://script.google.com
 * 2. Buat project baru
 * 3. Copy-paste kode ini ke Code.gs
 * 4. Klik tombol Run ▶️ dan pilih fungsi setupSIMKEUSpreadsheet()
 * 5. Berikan izin (authorize) jika diminta
 * 6. Lihat URL di View > Logs
 * 7. Spreadsheet akan dibuat di Google Drive Anda
 */

function setupSIMKEUSpreadsheet() {
  const SPREADSHEET_NAME = "DATABASE SIMKEU KECAMATAN CANDISARI 2027";
  
  // Definisi semua worksheet dengan header dan data contoh
  const worksheets = [
    {
      name: "PENGGUNA",
      headers: ["User Name", "Password", "Nama", "Peran"],
      sampleData: [
        ["admin", "admin123", "Admin Sistem", "ADMIN"],
        ["kasubag", "kasubag123", "Kasubag PEM", "KASUBAG_PEK"],
        ["pptk1", "pptk123", "PPTK Kecamatan", "PPTK"]
      ]
    },
    {
      name: "MASTER_WILAYAH",
      headers: ["Nama Wilayah", "Kode Wilayah"],
      sampleData: [
        ["Kecamatan Candisari", "KC01"],
        ["Kelurahan Candisari", "KL01"],
        ["Kelurahan Jebres", "KL02"],
        ["Kelurahan Laweyan", "KL03"]
      ]
    },
    {
      name: "MASTER_REKENING",
      headers: ["Kode Rekening", "Uraian Rekening"],
      sampleData: [
        ["5.2.1.01", "Honorarium PPTK"],
        ["5.2.1.02", "Bahan Tulis Kantor"],
        ["5.2.1.03", "Sewa Peralatan Kantor"],
        ["5.2.1.04", "Transportasi Dinas"],
        ["5.2.1.05", "Listrik dan Telepon"]
      ]
    },
    {
      name: "MASTER_SUB_KEGIATAN",
      headers: ["Kode Sub Kegiatan", "Sub Kegiatan", "Pagu Awal", "Sisa Pagu"],
      sampleData: [
        ["SK001", "Pembinaan Keuangan Desa", 50000000, '=C2 - SUMIFS(TRANSAKSI!G:G, TRANSAKSI!B:B, A2 & "*", TRANSAKSI!K:K, "Disetujui")'],
        ["SK002", "Pengawasan Keuangan", 30000000, '=C3 - SUMIFS(TRANSAKSI!G:G, TRANSAKSI!B:B, A3 & "*", TRANSAKSI!K:K, "Disetujui")'],
        ["SK003", "Pelaporan Keuangan", 20000000, '=C4 - SUMIFS(TRANSAKSI!G:G, TRANSAKSI!B:B, A4 & "*", TRANSAKSI!K:K, "Disetujui")']
      ]
    },
    {
      name: "TRANSAKSI",
      headers: [
        "NO", "SUB KEGIATAN", "KODE REKENING BELANJA",
        "PENGELOMPOKAN BELANJA (#)", "URAIAN",
        "JENIS TRANSAKSI (UP/GU/LS)", "NOMINAL",
        "TANGGAL PENGAJUAN", "BUKTI DUKUNG SPJ", "PPTK",
        "STATUS", "DIPUTUSKAN_OLEH", "TANGGAL_APPROVAL"
      ],
      sampleData: []
    },
    {
      name: "PERUBAHAN_PAGU",
      headers: [
        "SUB KEGIATAN", "PAGU BARU", "ALASAN",
        "DIAJUKAN OLEH", "TANGGAL AJUAN", "STATUS"
      ],
      sampleData: []
    }
  ];
  
  // Cek apakah spreadsheet sudah ada
  const existing = DriveApp.getFilesByName(SPREADSHEET_NAME);
  if (existing.hasNext()) {
    const spreadsheet = SpreadsheetApp.open(existing.next());
    Logger.log(
      "Spreadsheet sudah ada!\n" +
      "Nama: " + SPREADSHEET_NAME + "\n" +
      "URL: " + spreadsheet.getUrl()
    );
    return spreadsheet;
  }
  
  // Buat spreadsheet baru
  const spreadsheet = SpreadsheetApp.create(SPREADSHEET_NAME);
  const url = spreadsheet.getUrl();
  
  // Gunakan sheet default "Sheet1" sebagai worksheet pertama (tidak boleh dihapus semua sheet)
  const defaultSheet = spreadsheet.getSheets()[0];
  const firstWs = worksheets[0];
  defaultSheet.setName(firstWs.name);
  
  // Tulis header ke sheet pertama
  const headerRange = defaultSheet.getRange(1, 1, 1, firstWs.headers.length);
  headerRange.setValues([firstWs.headers]);
  headerRange.setFontWeight("bold");
  headerRange.setBackground("#1f77b4");
  headerRange.setFontColor("#ffffff");
  headerRange.setHorizontalAlignment("center");
  headerRange.setVerticalAlignment("middle");
  
  // Tulis data contoh ke sheet pertama (jika ada)
  if (firstWs.sampleData.length > 0) {
    const dataRange = defaultSheet.getRange(2, 1, firstWs.sampleData.length, firstWs.headers.length);
    dataRange.setValues(firstWs.sampleData);
  }
  
  defaultSheet.autoResizeColumns(1, firstWs.headers.length);
  defaultSheet.setFrozenRows(1);
  
  // Buat worksheet sisanya (mulai dari index 1)
  for (let i = 1; i < worksheets.length; i++) {
    const ws = worksheets[i];
    const sheet = spreadsheet.insertSheet(ws.name);
    
    // Tulis header
    const headerRange = sheet.getRange(1, 1, 1, ws.headers.length);
    headerRange.setValues([ws.headers]);
    
    // Format header: bold, background biru, teks putih
    headerRange.setFontWeight("bold");
    headerRange.setBackground("#1f77b4");
    headerRange.setFontColor("#ffffff");
    headerRange.setHorizontalAlignment("center");
    headerRange.setVerticalAlignment("middle");
    
    // Tulis data contoh (jika ada)
    if (ws.sampleData.length > 0) {
      const dataRange = sheet.getRange(2, 1, ws.sampleData.length, ws.headers.length);
      dataRange.setValues(ws.sampleData);
    }
    
    // Auto-resize kolom
    sheet.autoResizeColumns(1, ws.headers.length);
    
    // Freeze baris header
    sheet.setFrozenRows(1);
  }
  
  // Buat worksheet AUDIT_LOG (kosong, akan diisi oleh aplikasi)
  const auditSheet = spreadsheet.insertSheet("AUDIT_LOG");
  const auditHeaders = ["WAKTU", "USER", "AKSI", "TABEL", "RECORD_ID", "OLD VALUES", "NEW VALUES"];
  const auditHeaderRange = auditSheet.getRange(1, 1, 1, auditHeaders.length);
  auditHeaderRange.setValues([auditHeaders]);
  auditHeaderRange.setFontWeight("bold");
  auditHeaderRange.setBackground("#ff7f0e");
  auditHeaderRange.setFontColor("#ffffff");
  auditHeaderRange.setHorizontalAlignment("center");
  auditSheet.setFrozenRows(1);
  auditSheet.autoResizeColumns(1, auditHeaders.length);
  
  // Format semua worksheet: wrap teks, alignment
  const allSheets = spreadsheet.getSheets();
  for (let j = 0; j < allSheets.length; j++) {
    const sheet = allSheets[j];
    const dataRange = sheet.getDataRange();
    dataRange.setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
    dataRange.setVerticalAlignment("top");
  }
  
  // Log hasil ke Logger (lihat di View > Logs)
  Logger.log("✅ Spreadsheet SIMKEU berhasil dibuat!");
  Logger.log("Nama: " + SPREADSHEET_NAME);
  Logger.log("URL: " + url);
  Logger.log("Worksheet yang dibuat:");
  Logger.log("- PENGGUNA");
  Logger.log("- MASTER_WILAYAH");
  Logger.log("- MASTER_REKENING");
  Logger.log("- MASTER_SUB_KEGIATAN");
  Logger.log("- TRANSAKSI");
  Logger.log("- PERUBAHAN_PAGU");
  Logger.log("- AUDIT_LOG");
  Logger.log("");
  Logger.log("Langkah berikutnya:");
  Logger.log("1. Share spreadsheet ini ke email Service Account (akses Editor)");
  Logger.log("2. Masukkan URL spreadsheet ke .streamlit/secrets.toml");
  Logger.log("3. Jalankan aplikasi: streamlit run streamlit_app.py");
  
  return spreadsheet;
}

/**
 * Fungsi tambahan: Tambahkan user baru ke sheet PENGGUNA
 * @param {string} userName - Username
 * @param {string} password - Password
 * @param {string} nama - Nama lengkap
 * @param {string} peran - Peran (ADMIN / KASUBAG_PEK / PPTK)
 */
function addUser(userName, password, nama, peran) {
  const spreadsheet = SpreadsheetApp.openById(
    DriveApp.getFilesByName("DATABASE SIMKEU KECAMATAN CANDISARI 2027").next().getId()
  );
  const sheet = spreadsheet.getSheetByName("PENGGUNA");
  sheet.appendRow([userName, password, nama, peran]);
  Logger.log("User berhasil ditambahkan: " + userName);
}

/**
 * Fungsi tambahan: Dapatkan URL spreadsheet
 */
function getSpreadsheetURL() {
  const file = DriveApp.getFilesByName("DATABASE SIMKEU KECAMATAN CANDISARI 2027");
  if (file.hasNext()) {
    const spreadsheet = SpreadsheetApp.open(file.next());
    Logger.log("URL Spreadsheet: " + spreadsheet.getUrl());
    Logger.log("Nama: " + spreadsheet.getName());
  } else {
    Logger.log("Spreadsheet belum ditemukan. Jalankan setupSIMKEUSpreadsheet() terlebih dahulu.");
  }
}
