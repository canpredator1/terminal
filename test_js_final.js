const fs = require('fs');
const html = fs.readFileSync('data/output/relationship_map_v2.html', 'utf8');

// Use regex to get the script content
const scriptMatch = html.match(/<script>(.*?)<\/script>/s);
if (scriptMatch) {
    const code = scriptMatch[1];
    
    // We want to run this in JSDOM, but stub out d3 so it doesn't fail on d3 being missing.
    // Actually, let's just load d3 and ChartJS into JSDOM!
    
    const jsdom = require("jsdom");
    const { JSDOM } = jsdom;
    
    // Create a fully fledged DOM with d3 and chart.js loaded from node_modules if possible,
    // or just stub them in the HTML before passing to JSDOM.
    
    let safeHtml = html
        .replace('<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>', '<script>window.Chart = class { constructor() {} }; Chart.defaults={font:{}};</script>')
        .replace('<script src="https://d3js.org/d3.v7.min.js"></script>', '<script>window.d3 = { select: ()=>({ call:()=>({}), on:()=>({}), style:()=>({}), text:()=>({}), attr:()=>({}) }), zoom: ()=>({ on:()=>({}) }), forceSimulation: ()=>({ force:()=>({}), on:()=>({}) }), forceLink: ()=>({ id:()=>({}) }), forceManyBody: ()=>({}), forceCenter: ()=>({}), forceCollide: ()=>({}), drag: ()=>({ on:()=>({}) }), zoomIdentity: {translate:()=>({scale:()=>({translate:()=>({})})})} };</script>');
    
    const dom = new JSDOM(safeHtml, { runScripts: "dangerously" });
    
    setTimeout(() => {
        try {
            console.log("DOM loaded. Trying to click NVDA...");
            const window = dom.window;
            
            // find the node
            const d = window.graphData.nodes.find(n => n.id === "NVDA");
            if (!d) throw new Error("NVDA not found");
            
            window.openSidePanel(d);
            console.log("NVDA opened successfully");
            console.log("HTML length inside side panel:", window.document.getElementById("sp-content").innerHTML.length);
            
            // Loop all
            for(let n of window.graphData.nodes) {
                window.openSidePanel(n);
            }
            console.log("ALL NODES OPENED SAFELY!");
        } catch(e) {
            console.log("CRASH:", e);
        }
    }, 1000);
}
