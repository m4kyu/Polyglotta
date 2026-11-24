// Orthographic projection for the decorative atlas on the dashboard.
export function drawGlobe(canvas) {
  const {width, height} = canvas.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext("2d");
  ctx.scale(scale, scale);
  const r = Math.min(width * .40, height * .84), x = width * .54, y = height * .60;
  const rad = Math.PI / 180, tilt = 18 * rad;
  function project(lon, lat) {
    const a = (lon - 5) * rad, b = lat * rad;
    const z = Math.cos(b) * Math.cos(a);
    return [x + r * Math.cos(b) * Math.sin(a),
      y - r * (Math.sin(b) * Math.cos(tilt) - z * Math.sin(tilt)),
      Math.sin(b) * Math.sin(tilt) + z * Math.cos(tilt)];
  }
  ctx.fillStyle = "#98c89512";
  ctx.beginPath(); ctx.arc(x,y,r,0,2*Math.PI); ctx.fill();
  function line(points, color) {
    ctx.strokeStyle = color;
    ctx.beginPath();
    let visible = false;
    for (const [lon, lat] of points) {
      const [px,py,z] = project(lon,lat);
      if (z >= 0) { if (visible) ctx.lineTo(px,py); else ctx.moveTo(px,py); }
      visible = z >= 0;
    }
    ctx.stroke();
  }
  for (let a=-180;a<180;a+=15) line(Array.from({length:91},(_,i)=>[a,i*2-90]),"#b8d59b45");
  for (let b=-75;b<=75;b+=15) line(Array.from({length:181},(_,i)=>[i*2-180,b]),"#b8d59b45");
  const lands = [
    [[-17,15],[-16,22],[-10,29],[-6,36],[2,37],[11,37],[12,33],[20,32],[25,31],[32,31],[35,24],[43,12],[51,12],[50,4],[42,-3],[40,-12],[35,-18],[35,-24],[28,-33],[19,-35],[16,-29],[12,-17],[13,-8],[9,-2],[10,4],[3,6],[-2,5],[-8,5],[-15,11],[-17,15]],
    [[-10,36],[-9,43],[-2,44],[-5,48],[1,50],[5,53],[8,54],[8,58],[12,56],[12,61],[5,59],[8,63],[20,70],[30,71],[42,68],[63,69],[80,73],[88,62],[77,48],[86,29],[80,9],[73,16],[67,25],[58,25],[55,17],[44,12],[36,29],[33,31],[29,37],[24,40],[23,36],[19,40],[14,45],[17,40],[15,38],[12,42],[8,44],[4,43],[2,41],[-1,38],[-10,36]],
    [[-80,9],[-72,12],[-60,9],[-50,1],[-36,-5],[-39,-18],[-48,-28],[-57,-38],[-65,-55],[-72,-50],[-72,-35],[-76,-17],[-81,-5],[-80,9]],
    [[-9,50],[-6,55],[-5,59],[-2,57],[1,52],[-9,50]], [[44,-25],[44,-19],[50,-13],[48,-21],[44,-25]],
    [[-52,60],[-58,68],[-69,77],[-46,83],[-20,81],[-25,71],[-42,63],[-52,60]]
  ];
  for (const points of lands) {
    const coords = points.map(p=>project(...p));
    if (coords.every(p=>p[2]>=0)) {
      ctx.beginPath(); coords.forEach(([px,py],i)=>i?ctx.lineTo(px,py):ctx.moveTo(px,py));
      ctx.closePath(); ctx.fillStyle="#afd09838"; ctx.fill();
    }
    line(points,"#c0db9b9c");
  }
  ctx.strokeStyle="#bad8a481"; ctx.beginPath(); ctx.arc(x,y,r,0,Math.PI*2);ctx.stroke();
  ctx.setLineDash([3,5]);ctx.beginPath();ctx.ellipse(x,y,r*1.48,r*.36,-.38,0,Math.PI*2);ctx.stroke();
}
