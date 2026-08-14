const fileInput = document.getElementById('dataset-upload');
const fileDropArea = document.querySelector('.file-drop-area');
const fileMsg = document.querySelector('.file-msg');
const uploadBtn = document.getElementById('upload-btn');

const insightsBtn = document.getElementById('insights-btn');
const reportsSection = document.getElementById('reports-section');
const btnYdata = document.getElementById('btn-ydata');
const btnSweetviz = document.getElementById('btn-sweetviz');

const loader = document.getElementById('loader');
const loaderText = document.getElementById('loader-text');
const statusIndicator = document.getElementById('status-indicator');

const kpiGrid = document.getElementById('kpi-grid');
const chartsGrid = document.getElementById('charts-grid');
const insightsPanel = document.getElementById('insights-panel');
const insightsContent = document.getElementById('insights-content');

let selectedFile = null;

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    fileDropArea.addEventListener(eventName, preventDefaults, false);
});
function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
    fileDropArea.addEventListener(eventName, () => fileDropArea.classList.add('is-active'), false);
});
['dragleave', 'drop'].forEach(eventName => {
    fileDropArea.addEventListener(eventName, () => fileDropArea.classList.remove('is-active'), false);
});

fileDropArea.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles(files);
});

fileInput.addEventListener('change', function(e) {
    handleFiles(this.files);
});

function handleFiles(files) {
    if (files.length > 0) {
        selectedFile = files[0];
        fileMsg.textContent = selectedFile.name;
        uploadBtn.disabled = false;
        uploadBtn.textContent = "Upload & Analyze Data";
    }
}

uploadBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);

    showLoader('Cleaning Data & Generating Reports (Takes a moment)...');
    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.error || 'Upload failed');
        
        statusIndicator.textContent = 'Dataset Active: ' + selectedFile.name;
        statusIndicator.style.color = '#4cc9f0';
        statusIndicator.style.borderColor = '#4cc9f0';

        renderKPIs(data.kpis);

        if (data.charts && data.charts.length) {
            renderCharts(data.charts);
        } else {
            await fetchCharts();
        }

        if (data.insights) {
            insightsPanel.classList.remove('hidden');
            insightsContent.innerHTML = marked.parse(data.insights);
        }

        if (data.reports) {
            btnYdata.href = data.reports.ydata;
            btnSweetviz.href = data.reports.sweetviz;
            reportsSection.classList.remove('hidden');
        }

        insightsBtn.disabled = false;
    } catch (error) {
        alert("Error: " + error.message);
    } finally {
        hideLoader();
    }
});

function renderKPIs(kpis) {
    kpiGrid.innerHTML = '';
    let count = 0;
    for (const [key, value] of Object.entries(kpis)) {
        if (count >= 12) break;
        const card = document.createElement('div');
        card.className = 'kpi-card';
        card.innerHTML = `
            <div class="kpi-value">${typeof value === 'number' && !Number.isInteger(value) ? value.toFixed(2) : value}</div>
            <div class="kpi-label">${key}</div>
        `;
        kpiGrid.appendChild(card);
        count++;
    }
}

async function fetchCharts() {
    showLoader('Generating Intelligent Charts...');
    try {
        const res = await fetch('/api/charts');
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.error);

        renderCharts(data.charts);
    } catch (error) {
        console.error("Charts error:", error);
    } finally {
        hideLoader();
    }
}

function decodeBData(obj) {
    const binary = atob(obj.bdata);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    
    const buffer = bytes.buffer;
    switch(obj.dtype) {
        case 'f8': return Array.from(new Float64Array(buffer));
        case 'f4': return Array.from(new Float32Array(buffer));
        case 'i8': return Array.from(new BigInt64Array(buffer)).map(Number);
        case 'i4': return Array.from(new Int32Array(buffer));
        case 'i2': return Array.from(new Int16Array(buffer));
        case 'i1': return Array.from(new Int8Array(buffer));
        case 'u8': return Array.from(new BigUint64Array(buffer)).map(Number);
        case 'u4': return Array.from(new Uint32Array(buffer));
        case 'u2': return Array.from(new Uint16Array(buffer));
        case 'u1': return Array.from(new Uint8Array(buffer));
        default: return Array.from(new Float64Array(buffer));
    }
}

function processBDataRecursively(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj.bdata && obj.dtype) return decodeBData(obj);
    
    if (Array.isArray(obj)) {
        for (let i = 0; i < obj.length; i++) obj[i] = processBDataRecursively(obj[i]);
    } else {
        for (let key in obj) {
            if (Object.prototype.hasOwnProperty.call(obj, key)) {
                obj[key] = processBDataRecursively(obj[key]);
            }
        }
    }
    return obj;
}

function renderCharts(chartsData) {
    chartsGrid.innerHTML = '';
    if (!chartsData || !chartsData.length) {
        const empty = document.createElement('div');
        empty.className = 'chart-container';
        empty.textContent = 'No charts could be generated for this file. Check that the sheet has a header row and data columns.';
        chartsGrid.appendChild(empty);
        return;
    }
    chartsData.forEach((chartData, index) => {
        const container = document.createElement('div');
        container.id = `chart-${index}`;
        container.className = 'chart-container';
        chartsGrid.appendChild(container);

        const cleanedData = processBDataRecursively(chartData.data);
        const layout = processBDataRecursively(chartData.layout || {});
        Plotly.newPlot(container.id, cleanedData, layout, {responsive: true, displayModeBar: false});
    });
}

insightsBtn.addEventListener('click', async () => {
    showLoader('AI is analyzing the data...');
    try {
        const res = await fetch('/api/insights', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.error);

        insightsPanel.classList.remove('hidden');
        insightsContent.innerHTML = marked.parse(data.insights);
        
        insightsPanel.scrollIntoView({behavior: 'smooth'});

    } catch (error) {
        alert("Insights error: " + error.message);
    } finally {
        hideLoader();
    }
});

function showLoader(msg) {
    loaderText.textContent = msg;
    loader.classList.remove('hidden');
}

function hideLoader() {
    loader.classList.add('hidden');
}
