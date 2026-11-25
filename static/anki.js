const ratings = ["Again", "Hard", "Good", "Easy"];
const answers = row => row.slice(0, 4).reduce((sum, value) => sum + value, 0);

function studyTime(milliseconds) {
  const seconds = Math.round(milliseconds / 1000);
  return seconds < 60 ? seconds + "s" : Math.floor(seconds / 60) + "m " + seconds % 60 + "s";
}

export function progressPanel(info, escape, action, days) {
  const header = '<section class="panel anki"><div class="panelhead"><h2>Anki progress</h2>';
  if (!info?.linked) return header+'</div><p>Open Account → Anki to connect your devices.</p></section>';
  const manage = info.decks.length ? action("anki-decks","Map decks") : "";
  const notice = info.message ? '<p role="status">'+escape(info.message)+'</p>' : "";
  if (!info.updated) return header+'</div>'+notice+'<p>Waiting for the first collection sync.</p></section>';
  const updated = '<small>'+ (info.stale ? 'Snapshot delayed · ' : '')+'Updated '+escape(new Date(info.updated*1000).toLocaleString())+'</small>';
  if (!info.mapped.length) return header+manage+'</div>'+notice+'<p>Choose decks for this language to see your reviews.</p>'+updated+'</section>';

  const series = Object.entries(info.days);
  const peak = Math.max(1,...series.map(([,row])=>answers(row)));
  const [lastDay,today] = series.at(-1);
  const ranges = [7, 30, 90, 180].map(value =>
    action("anki-range", value + "D", value, value === days ? "active" : "")
  ).join("");
  const bars = series.map(([date,row])=>{
    const label = date+' · '+ratings.map((r,i)=>r+' '+row[i]).join(', ');
    return '<div class="anki-day" tabindex="0" aria-label="'+label+'" title="'+label+'">'+row.slice(0,4).map((n,i)=>'<i class="rating-'+i+'" style="height:'+100*n/peak+'%"></i>').join('')+'</div>';
  }).join('');
  const active = series.filter(([,row])=>answers(row)>0).length;
  const legend = ratings.map((name,index)=>'<span><i class="anki-key rating-'+index+'"></i>'+name+'</span>').join('');
  return header+manage+'</div>'+notice+
    '<div class="panelhead"><span>Review history</span><div class="seg">'+ranges+'</div></div><div class="anki-summary"><div><small>Study day · '+lastDay+'</small><strong>'+answers(today)+' reviews</strong></div>'+
    '<div><small>Recorded study time</small><strong>'+studyTime(today[4])+'</strong></div>'+
    '<div><small>Active study days</small><strong>'+active+' / '+series.length+'</strong></div></div>'+
    '<div class="anki-bars">'+bars+'</div><div class="anki-axis"><small>'+series[0][0]+'</small><small>'+lastDay+'</small></div>'+
    '<div class="anki-legend">'+legend+'</div>'+updated+'</section>';
}
