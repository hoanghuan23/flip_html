// Có thể chỉnh sửa số liệu hoặc độ cao cột tại đây.
const data = [
  { label: 'Tháng 5', value: '150,9 mm', change: '−35,9%', height: 24, positive: false },
  { label: 'Tháng 6', value: '168,3 mm', change: '−29,5%', height: 28, positive: false },
  { label: 'Tháng 7', value: '152,9 mm', change: '−36,5%', height: 24.5, positive: false },
  { label: 'Tháng 8', value: '127,5 mm', change: '−53,1%', height: 20, positive: false },
  { label: 'Tháng 9', value: '476,6 mm', change: '+48,8%', height: 82, positive: true },
  { label: '1-6/10', value: '203,9 mm', change: '+192,7%', height: 33, positive: true }
];

const columns = document.getElementById('columns');
columns.innerHTML = data.map(item => `
  <section class="column" style="--height: ${item.height}%" aria-label="${item.label}: ${item.value}, ${item.change}">
    <div class="column__fill" aria-hidden="true"></div>
    <div class="column__data">
      <span class="column__value">${item.value}</span>
      <span class="column__change ${item.positive ? 'column__change--positive' : ''}">${item.change}</span>
    </div>
    <div class="column__label">${item.label}</div>
  </section>
`).join('');
