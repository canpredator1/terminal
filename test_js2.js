const fs = require('fs');
const html = fs.readFileSync('data/output/relationship_map_v2.html', 'utf8');
const scriptMatch = html.match(/<script>(.*?)<\/script>/s);
if(scriptMatch) {
    const code = scriptMatch[1];
    
    // We want to run the whole code basically
    // but without DOM dependencies throwing errors before we test click.
    
    // But it's easier to just find the data and run populateSidePanel.
    const fnMatch = code.match(/(function populateSidePanel.*?)(?=\n  function |\n  \/\/)/s);
    const dataMatch = code.match(/const graphData = (.*?);/s);
    
    if(fnMatch && dataMatch) {
        let fnCode = fnMatch[1];
        let graphDataStr = dataMatch[1];
        
        const wrapper = `
        const document = { 
            getElementById: (id) => {
                return { 
                    innerHTML: '', 
                    classList: { add:()=>{} }, 
                    getContext: ()=>({}) 
                };
            }
        };
        const graphData = ${graphDataStr};
        let radarChart = { destroy: ()=>{} };
        const Chart = { defaults: { font: {} } };
        class ChartClass { constructor(){} };
        function updateHighlight(){}
        function generateGridHTML(){ return ''; }
        let clickedNode = null;
        
        ` + fnCode.replace(/new Chart\(/g, 'new ChartClass(') + `
        
        try {
            // try NVDA
            populateSidePanel({id:"NVDA"});
            console.log("NVDA OK");
            populateSidePanel({id:"TSM"});
            console.log("TSM OK");
            // Try all nodes
            for(let node of graphData.nodes) {
                populateSidePanel({id: node.id});
            }
            console.log("ALL NODES OK");
        } catch(e) {
            console.log('Runtime error:', e);
        }
        `;
        
        try {
            eval(wrapper);
        } catch(e) {
            console.log('Eval error:', e);
        }
    } else {
        console.log("Regex fail");
    }
}
