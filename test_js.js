const fs = require('fs');
const html = fs.readFileSync('data/output/relationship_map_v2.html', 'utf8');
const scriptMatch = html.match(/<script>(.*?)<\/script>/s);
if(scriptMatch) {
    const code = scriptMatch[1];
    const fnMatch = code.match(/(function populateSidePanel.*?)(?=\n  function |\n  \/\/)/s);
    if(fnMatch) {
        let fnCode = fnMatch[1];
        const wrapper = `
        const document = { 
            getElementById: (id) => {
                return { innerHTML: '', classList: { add:()=>{} }, getContext: ()=>({}) };
            }
        };
        const graphData = { 
            details: { 
                'TSM': { 
                    master: { ai_exposure_score: 1 }, 
                    sentiment: {}, 
                    news: [{published_at: '2026-06-15T', url: '', headline: '', source: ''}] 
                } 
            } 
        };
        let radarChart = { destroy: ()=>{} };
        const Chart = { defaults: { font: {} } };
        class ChartClass { constructor(){} };
        function updateHighlight(){}
        ` + fnCode.replace('new Chart(', 'new ChartClass(') + '; populateSidePanel({id:"TSM"});';
        try {
            eval(wrapper);
            console.log('Ran successfully');
        } catch(e) {
            console.log('Runtime error:', e);
        }
    } else {
        console.log('Could not find fn');
    }
}
