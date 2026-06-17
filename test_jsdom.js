const fs = require('fs');
const html = fs.readFileSync('data/output/relationship_map_v2.html', 'utf8');

// We will inject a script into the HTML string itself to test it, and then load it via JSDOM.
// Let's just manually search for the openSidePanel function inside the html and execute it.
const jsdom = require("jsdom");
const { JSDOM } = jsdom;

const dom = new JSDOM(html, { runScripts: "dangerously" });
setTimeout(() => {
    try {
        console.log("Testing click on NVDA...");
        const window = dom.window;
        const d = window.graphData.nodes.find(n => n.id === "NVDA");
        window.openSidePanel(d);
        console.log("NVDA clicked successfully");
        
        console.log("Testing click on ALL nodes...");
        for(let node of window.graphData.nodes) {
            window.openSidePanel(node);
        }
        console.log("ALL NODES OK");
    } catch(e) {
        console.log("ERROR DURING CLICK:", e);
    }
}, 1000);
