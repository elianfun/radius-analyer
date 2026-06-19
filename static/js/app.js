// 全域工具：將 ISO datetime 轉為本地時間顯示
function formatDate(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleString('zh-TW');
}
