const fs = require('fs');
const { JSDOM } = require('jsdom');

const html = fs.readFileSync('data/output/relationship_map.html', 'utf8');
const dom = new JSDOM(html, { runScripts: "dangerously", resources: "usable" });

dom.window.addEventListener('error', (event) => {
    console.error("JS Error:", event.error);
});

setTimeout(() => {
    console.log("Nodes count:", dom.window.document.querySelectorAll('circle').length);
    console.log("Stats count:", dom.window.document.getElementById('node-count').textContent);
    process.exit(0);
}, 2000);
