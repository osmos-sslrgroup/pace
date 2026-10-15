const API_BASE = window.location.protocol === 'file:' ? 'http://127.0.0.1:8000' : window.location.origin;
window.isProjectDirty = false;

// Login state management
window.addEventListener('DOMContentLoaded', () => {
    const authData = sessionStorage.getItem('pace_auth');
    if (!authData) {
        document.getElementById('login-overlay').style.display = 'flex';
    } else {
        document.getElementById('login-overlay').style.display = 'none';
    }
});

window.handleLoginSubmit = async function(e) {
    e.preventDefault();
    const u = document.getElementById('login-username').value;
    const p = document.getElementById('login-password').value;
    const encoded = btoa(u + ':' + p);
    
    document.getElementById('login-submit-btn').innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Signing in...';
    document.getElementById('login-error').style.display = 'none';
    
    try {
        const res = await fetch(`${API_BASE}/api/verify-auth`, {
            method: 'POST',
            headers: { 'Authorization': `Basic ${encoded}` }
        });
        
        if (res.ok) {
            sessionStorage.setItem('pace_auth', encoded);
            document.getElementById('login-overlay').style.display = 'none';
        } else {
            document.getElementById('login-error').style.display = 'block';
        }
    } catch (err) {
        document.getElementById('login-error').innerText = 'Network error connecting to server.';
        document.getElementById('login-error').style.display = 'block';
    } finally {
        document.getElementById('login-submit-btn').innerHTML = 'Sign In';
    }
};

window.showLoader = function() {
    const loader = document.getElementById('global-loader');
    if (loader) {
        loader.classList.add('is-active');
        const loaderContainer = loader.querySelector('.pace-loader');
        if (loaderContainer) {
            loaderContainer.style.transform = 'none';
        }
    }
};

window.hideLoader = function() {
    const loader = document.getElementById('global-loader');
    if (loader) loader.classList.remove('is-active');
};

const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const url = args[0];
    const isCalc = url && typeof url === 'string' && (
        url.includes('/calculate') || 
        url.includes('/process-recommendation') || 
        url.includes('/simulate-aging')
    );

    if (isCalc && window.showLoader) window.showLoader();
    const startTime = Date.now();
    try {
        if (url && typeof url === 'string' && (url.includes('localhost:8000') || url.includes('/api/') || url.includes('robust-integrity'))) {
            const auth = sessionStorage.getItem('pace_auth');
            if (auth) {
                const opts = args[1] || {};
                opts.headers = opts.headers || {};
                
                if (opts.headers instanceof Headers) {
                    opts.headers.set('Authorization', `Basic ${auth}`);
                } else {
                    opts.headers['Authorization'] = `Basic ${auth}`;
                }
                args[1] = opts;
            }
        }
        return await originalFetch(...args);
    } finally {
        if (isCalc) {
            const elapsed = Date.now() - startTime;
            if (elapsed < 1500) {
                await new Promise(r => setTimeout(r, 1500 - elapsed));
            }
            if (window.hideLoader) window.hideLoader();
        }
    }
};

window.isAppUnlocked = false;

window.validateProjectModal = function() {
    const pName = document.getElementById('proj-name');
    const hasProjectName = pName && pName.value.trim() !== '';

    // If project name is empty, relock the app immediately
    if (!hasProjectName) {
        window.isAppUnlocked = false;
    }

    if (window.isAppUnlocked && hasProjectName) {
        document.querySelectorAll('.pace-locked-tab').forEach(btn => {
            btn.classList.remove('pace-locked-tab');
            const icon = btn.querySelector('.pace-lock-icon');
            if (icon) icon.style.display = 'none';
        });
        const memBtn = document.getElementById('membrane-db-btn');
        if (memBtn) {
            memBtn.classList.remove('pace-locked-tab');
            const icon = memBtn.querySelector('.pace-lock-icon');
            if (icon) icon.style.display = 'none';
        }
        window.isProjectDirty = true;
    } else {
        // Lock all tabs other than file and project-details
        document.querySelectorAll('.menu-btn:not(#project-details-tab-btn):not(#file-tab-btn)').forEach(btn => {
            btn.classList.add('pace-locked-tab');
            const icon = btn.querySelector('.pace-lock-icon');
            if (icon) icon.style.display = 'inline-block';
        });
        const memBtn = document.getElementById('membrane-db-btn');
        if (memBtn) {
            memBtn.classList.add('pace-locked-tab');
            const icon = memBtn.querySelector('.pace-lock-icon');
            if (icon) icon.style.display = 'inline-block';
        }
    }
};

window.clearProjectModal = function() {
    const pName = document.getElementById('proj-name');
    const pEng = document.getElementById('proj-engineer');
    const pId = document.getElementById('proj-id');
    if (pName) pName.value = '';
    if (pEng) pEng.value = '';
    if (pId) {
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, '0');
        const dd = String(now.getDate()).padStart(2, '0');
        const rand = Math.floor(1000 + Math.random() * 9000);
        pId.value = `PACE-${yyyy}-${mm}${dd}-${rand}`;
    }
    window.validateProjectModal();
};

window.proceedToApp = function() {
    const pName = document.getElementById('proj-name');
    if (pName && pName.value.trim() !== '') {
        window.isAppUnlocked = true;
        window.validateProjectModal();
        const feedTab = document.getElementById('feed-data-tab-btn');
        if (feedTab) feedTab.click();
    } else {
        alert('Please fill out the PROJECT NAME field first to proceed.');
    }
};

window.saveProjectDetails = async function(event) {
    if (event) event.preventDefault();
    window.validateProjectModal();
    const pName = document.getElementById('proj-name');
    if (pName && pName.value.trim() !== '') {
        const lastSaved = document.getElementById('proj-last-saved-status');
        if (lastSaved) {
            lastSaved.textContent = new Date().toLocaleTimeString();
            lastSaved.style.color = 'var(--success-color, #10b981)';
        }
        // Sync sticky footer bar
        const footerSaved = document.getElementById('footer-last-saved');
        if (footerSaved) footerSaved.textContent = new Date().toLocaleTimeString();
        const footerStatus = document.getElementById('footer-project-status');
        if (footerStatus) footerStatus.textContent = 'Saved';
        const statusDot = document.getElementById('footer-status-dot');
        if (statusDot) statusDot.style.background = '#10b981';
        
        // Collect all inputs, selects, and textareas
        const data = {};
        document.querySelectorAll('input, select, textarea').forEach(el => {
            if (el.id) {
                if (el.type === 'checkbox') {
                    data[el.id] = el.checked;
                } else if (el.type === 'radio') {
                    if (el.checked) data[el.name] = el.value; // Store radio groups by name
                } else if (el.type !== 'file') {
                    data[el.id] = el.value;
                }
            }
        });
        
        const jsonStr = JSON.stringify(data, null, 2);
        const fileName = (pName.value.trim().replace(/[^a-z0-9]/gi, '_').toLowerCase() || 'project') + '.prt';

        try {
            if ('showSaveFilePicker' in window) {
                const handle = await window.showSaveFilePicker({
                    suggestedName: fileName,
                    types: [{
                        description: 'PACE Project Files',
                        accept: {'application/json': ['.prt', '.json']},
                    }],
                });
                const writable = await handle.createWritable();
                await writable.write(jsonStr);
                await writable.close();
            } else {
                const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(jsonStr);
                const downloadAnchorNode = document.createElement('a');
                downloadAnchorNode.setAttribute("href", dataStr);
                downloadAnchorNode.setAttribute("download", fileName);
                document.body.appendChild(downloadAnchorNode); 
                downloadAnchorNode.click();
                downloadAnchorNode.remove();
            }
            window.isProjectDirty = false;
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error("Error saving project:", err);
                alert("An error occurred while saving the project.");
            }
        }
    } else {
        alert('Please provide a PROJECT NAME before saving.');
    }
};

window.startNewProject = function() {
    if (confirm('Are you sure you want to start a new project? All unsaved data will be lost.')) {
        window.isProjectDirty = false;
        window.location.reload();
    }
};

window.loadProjectFromFile = function() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.prt,.json';
    fileInput.onchange = e => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = e => {
            try {
                const data = JSON.parse(e.target.result);
                Object.keys(data).forEach(key => {
                    const el = document.getElementById(key);
                    if (el) {
                        if (el.type === 'checkbox') {
                            el.checked = data[key];
                        } else {
                            el.value = data[key];
                        }
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    } else {
                        // Check for radio buttons by name
                        const radios = document.querySelectorAll(`input[type="radio"][name="${key}"]`);
                        radios.forEach(radio => {
                            if (radio.value === data[key]) {
                                radio.checked = true;
                                radio.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        });
                    }
                });
                window.isProjectDirty = false;
                window.validateProjectModal();
                if (typeof calculateChemistry === 'function') calculateChemistry(true);
            } catch (err) {
                alert("Invalid project file.");
            }
        };
        reader.readAsText(file);
    };
    fileInput.click();
};

window.addEventListener('beforeunload', (e) => {
    if (window.isProjectDirty) {
        e.preventDefault();
        e.returnValue = '';
    }
});

document.addEventListener('input', () => { window.isProjectDirty = true; });

// Make sure to unlock on load if there's data
window.addEventListener('load', () => {
    const projIdInput = document.getElementById('proj-id');
    if (projIdInput && !projIdInput.value) {
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, '0');
        const dd = String(now.getDate()).padStart(2, '0');
        const rand = Math.floor(1000 + Math.random() * 9000);
        projIdInput.value = `PACE-${yyyy}-${mm}${dd}-${rand}`;
    }
    
    // Load saved User Info from LocalStorage
    const savedUserInfo = localStorage.getItem('pace_user_info');
    if (savedUserInfo) {
        try {
            const data = JSON.parse(savedUserInfo);
            if (document.getElementById('user-first-name')) document.getElementById('user-first-name').value = data.firstName || '';
            if (document.getElementById('user-last-name')) document.getElementById('user-last-name').value = data.lastName || '';
            if (document.getElementById('user-company')) document.getElementById('user-company').value = data.company || '';
            if (document.getElementById('user-email')) document.getElementById('user-email').value = data.email || '';
            if (document.getElementById('user-office')) document.getElementById('user-office').value = data.office || '';
            if (document.getElementById('user-mobile')) document.getElementById('user-mobile').value = data.mobile || '';
            if (document.getElementById('user-fax')) document.getElementById('user-fax').value = data.fax || '';
            if (document.getElementById('user-street')) document.getElementById('user-street').value = data.street || '';
            if (document.getElementById('user-city')) document.getElementById('user-city').value = data.city || '';
            if (document.getElementById('user-country')) document.getElementById('user-country').value = data.country || '';
            if (document.getElementById('user-ui-lang') && data.uiLang) document.getElementById('user-ui-lang').value = data.uiLang;
            if (document.getElementById('user-report-lang') && data.reportLang) document.getElementById('user-report-lang').value = data.reportLang;
            
            // Update initials
            let initials = '';
            if (data.firstName) initials += data.firstName[0];
            if (data.lastName) initials += data.lastName[0];
            initials = initials.toUpperCase() || 'JD';
            const profileBtn = document.querySelector('.user-profile');
            if (profileBtn) profileBtn.textContent = initials;
        } catch (e) {
            console.error('Error parsing saved user info', e);
        }
    } else {
        // Fallback: update initials from default DOM input values (e.g. Wave Tango -> WT)
        const fNameInput = document.getElementById('user-first-name');
        const lNameInput = document.getElementById('user-last-name');
        const fName = fNameInput ? fNameInput.value.trim() : '';
        const lName = lNameInput ? lNameInput.value.trim() : '';
        let initials = '';
        if (fName) initials += fName[0];
        if (lName) initials += lName[0];
        initials = initials.toUpperCase() || 'JD';
        const profileBtn = document.querySelector('.user-profile');
        if (profileBtn) profileBtn.textContent = initials;
    }
    
    // Check if project name is pre-populated on load to auto-unlock
    const pNameInput = document.getElementById('proj-name');
    if (pNameInput && pNameInput.value.trim() !== '') {
        window.isAppUnlocked = true;
    }

    // Wire up header "Run Analysis" button
    const runAnalysisBtn = document.getElementById('run-analysis-btn');
    if (runAnalysisBtn) {
        runAnalysisBtn.addEventListener('click', () => {
            const pName = document.getElementById('proj-name');
            if (!pName || pName.value.trim() === '') {
                alert('Please fill out the PROJECT NAME field first to proceed.');
                const projTab = document.getElementById('project-details-tab-btn');
                if (projTab) projTab.click();
                if (pName) pName.focus();
                return;
            }
            
            if (!window.isAppUnlocked) {
                alert('Please click the "SAVE & Proceed" button on the Project Details page first to unlock other modules.');
                const projTab = document.getElementById('project-details-tab-btn');
                if (projTab) projTab.click();
                return;
            }
            
            const feedTab = document.getElementById('feed-data-tab-btn');
            if (feedTab) {
                feedTab.click();
                if (typeof calculateChemistry === 'function') calculateChemistry(true);
                if (typeof calculatePreTreatment === 'function') calculatePreTreatment(true);
            }
        });
    }

    setTimeout(window.validateProjectModal, 500);
    if (typeof validatePhysicalParameters === 'function') {
        validatePhysicalParameters();
    }
});
window.roMembranes = {
        "HPA-4040": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 9.3,
            "permeability_A": 3.39,
            "permeability_B": 5.3e-08,
            "feed_spacer_mil": 34,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 4.09,
            "min_conc_flow_m3h": 0.91,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.102,
            "nominal_rejection": 0.996,
            "min_rejection": 0.995,
            "flags": [],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": {
                "Ca": 0.997,
                "Mg": 0.997,
                "Na": 0.988,
                "K": 0.983,
                "Cl": 0.988,
                "SO4": 0.998,
                "HCO3": 0.983,
                "Ba": 0.998,
                "Sr": 0.998,
                "F": 0.975,
                "SiO2": 0.990,
                "B": 0.770,
                "NO3": 0.945,
                "PO4": 0.997,
                "NH4": 0.890
            },
        },
        "HPA-RO-8040-LF-WW": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.367,
            "permeability_B": 3.89e-08,
            "feed_spacer_mil": 34,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.997,
            "min_rejection": 0.9960000000000001,
            "flags": ['LF'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": {
                "Ca": 0.997,
                "Mg": 0.997,
                "Na": 0.988,
                "K": 0.983,
                "Cl": 0.988,
                "SO4": 0.998,
                "HCO3": 0.983,
                "Ba": 0.998,
                "Sr": 0.998,
                "F": 0.975,
                "SiO2": 0.99,
                "B": 0.77,
                "NO3": 0.945,
                "PO4": 0.997,
                "NH4": 0.89,
            },
        },
        "HPA-RO-8040": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.213,
            "permeability_B": 3.72e-08,
            "feed_spacer_mil": 34,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.997,
            "min_rejection": 0.9960000000000001,
            "flags": [],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": {
                "Ca": 0.997,
                "Mg": 0.997,
                "Na": 0.988,
                "K": 0.983,
                "Cl": 0.988,
                "SO4": 0.998,
                "HCO3": 0.983,
                "Ba": 0.998,
                "Sr": 0.998,
                "F": 0.975,
                "SiO2": 0.99,
                "B": 0.77,
                "NO3": 0.945,
                "PO4": 0.997,
                "NH4": 0.89,
            },
        },
        "HPA-RO-LPM-8040-440": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 40.9,
            "permeability_A": 3.482,
            "permeability_B": 4.03e-08,
            "feed_spacer_mil": 28,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.997,
            "min_rejection": 0.9960000000000001,
            "flags": ['LPM'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": {
                "Ca": 0.997,
                "Mg": 0.997,
                "Na": 0.988,
                "K": 0.983,
                "Cl": 0.988,
                "SO4": 0.998,
                "HCO3": 0.983,
                "Ba": 0.998,
                "Sr": 0.998,
                "F": 0.975,
                "SiO2": 0.99,
                "B": 0.77,
                "NO3": 0.945,
                "PO4": 0.997,
                "NH4": 0.89,
            },
        },
        "HPARO-8040-BW-400": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.359,
            "permeability_B": 3.89e-08,
            "feed_spacer_mil": 31,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.997,
            "min_rejection": 0.9960000000000001,
            "flags": [],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": {
                "Ca": 0.997,
                "Mg": 0.997,
                "Na": 0.988,
                "K": 0.983,
                "Cl": 0.988,
                "SO4": 0.998,
                "HCO3": 0.983,
                "Ba": 0.998,
                "Sr": 0.998,
                "F": 0.975,
                "SiO2": 0.99,
                "B": 0.77,
                "NO3": 0.945,
                "PO4": 0.997,
                "NH4": 0.89,
            },
        },
        "HPARO-8040-LF": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.213,
            "permeability_B": 2.48e-08,
            "feed_spacer_mil": 34,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.998,
            "min_rejection": 0.997,
            "flags": ['LF'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": {
                "Ca": 0.997,
                "Mg": 0.997,
                "Na": 0.988,
                "K": 0.983,
                "Cl": 0.988,
                "SO4": 0.998,
                "HCO3": 0.983,
                "Ba": 0.998,
                "Sr": 0.998,
                "F": 0.975,
                "SiO2": 0.99,
                "B": 0.77,
                "NO3": 0.945,
                "PO4": 0.997,
                "NH4": 0.89,
            },
        },
        "HPARO-8040-LF2": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.52,
            "permeability_B": 2.71e-08,
            "feed_spacer_mil": 34,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.998,
            "min_rejection": 0.997,
            "flags": ['LF'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": {
                "Ca": 0.997,
                "Mg": 0.997,
                "Na": 0.988,
                "K": 0.983,
                "Cl": 0.988,
                "SO4": 0.998,
                "HCO3": 0.983,
                "Ba": 0.998,
                "Sr": 0.998,
                "F": 0.975,
                "SiO2": 0.99,
                "B": 0.77,
                "NO3": 0.945,
                "PO4": 0.997,
                "NH4": 0.89,
            },
        },
        "HPARO-8040-PRO-400": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.229,
            "permeability_B": 4.99e-08,
            "feed_spacer_mil": 34,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.996,
            "min_rejection": 0.995,
            "flags": [],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": {
                "Ca": 0.997,
                "Mg": 0.997,
                "Na": 0.988,
                "K": 0.983,
                "Cl": 0.988,
                "SO4": 0.998,
                "HCO3": 0.983,
                "Ba": 0.998,
                "Sr": 0.998,
                "F": 0.975,
                "SiO2": 0.99,
                "B": 0.77,
                "NO3": 0.945,
                "PO4": 0.997,
                "NH4": 0.89,
            },
        },
        "SWRO-8040-400": {
            "type": "SWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.5,
            "permeability_A": 1.075,
            "permeability_B": 1.76e-08,
            "feed_spacer_mil": 28,
            "max_pressure_bar": 55.2,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.998,
            "min_rejection": 0.997,
            "flags": [],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": {
                "Ca": 0.997,
                "Mg": 0.997,
                "Na": 0.995,
                "K": 0.983,
                "Cl": 0.995,
                "SO4": 0.998,
                "HCO3": 0.983,
                "Ba": 0.998,
                "Sr": 0.998,
                "F": 0.975,
                "SiO2": 0.99,
                "B": 0.85,
                "NO3": 0.945,
                "PO4": 0.997,
                "NH4": 0.89,
            },
        },
        "SWRO-FR-8040-400": {
            "type": "SWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 1.183,
            "permeability_B": 1.93e-08,
            "feed_spacer_mil": 34,
            "max_pressure_bar": 55.2,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.998,
            "min_rejection": 0.997,
            "flags": ['FR'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": {
                "Ca": 0.997,
                "Mg": 0.997,
                "Na": 0.995,
                "K": 0.983,
                "Cl": 0.995,
                "SO4": 0.998,
                "HCO3": 0.983,
                "Ba": 0.998,
                "Sr": 0.998,
                "F": 0.975,
                "SiO2": 0.99,
                "B": 0.85,
                "NO3": 0.945,
                "PO4": 0.997,
                "NH4": 0.89,
            },
        },
        "SWRO-HLE-8040-400": {
            "type": "SWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 1.297,
            "permeability_B": 2.12e-08,
            "feed_spacer_mil": 28,
            "max_pressure_bar": 55.2,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.998,
            "min_rejection": 0.997,
            "flags": ['HLE'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": {
                "Ca": 0.997,
                "Mg": 0.997,
                "Na": 0.995,
                "K": 0.983,
                "Cl": 0.995,
                "SO4": 0.998,
                "HCO3": 0.983,
                "Ba": 0.998,
                "Sr": 0.998,
                "F": 0.975,
                "SiO2": 0.99,
                "B": 0.85,
                "NO3": 0.945,
                "PO4": 0.997,
                "NH4": 0.89,
            },
        },

};

// Conversion and Calculation Engine
let currentUnits = {
    flow: 'm3/h',
    pressure: 'bar',
    temp: 'C',
    flux: 'LMH'
};

// Unit conversion helper functions
const conversions = {
    flow: {
        toBase: (val, unit) => {
            const factors = {'m3/h': 1, 'm3/d': 1/24, 'gpm': 0.227125, 'gpd': 0.0001577};
            return val * (factors[unit] || 1);
        },
        fromBase: (val, unit) => {
            const factors = {'m3/h': 1, 'm3/d': 24, 'gpm': 4.40287, 'gpd': 6340.13};
            return val * (factors[unit] || 1);
        }
    },
    pressure: {
        toBase: (val, unit) => {
            if (unit === 'psi') return val * 0.0689476;
            return val;
        },
        fromBase: (val, unit) => {
            if (unit === 'psi') return val * 14.5038;
            return val;
        }
    },
    temp: {
        toBase: (val, unit) => {
            if (unit === 'F') return (val - 32) * 5/9;
            return val;
        },
        fromBase: (val, unit) => {
            if (unit === 'F') return (val * 9/5) + 32;
            return val;
        }
    },
    flux: {
        toBase: (val, unit) => {
            if (unit === 'gfd') return val * 1.6977;
            return val;
        },
        fromBase: (val, unit) => {
            if (unit === 'gfd') return val * 0.589;
            return val;
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    // Add event listeners to all inputs to trigger live validation and prevent negatives
    const allInputs = document.querySelectorAll('input[type="number"]');
    allInputs.forEach(input => {
        input.setAttribute('min', '0');
        input.addEventListener('input', (e) => {
            if (parseFloat(e.target.value) < 0) {
                e.target.value = '';
            }
            validatePhysicalParameters();
            if (typeof calculateChemistry === 'function') {
                calculateChemistry(false);
            }
        });
    });

    // Feed Water Type Dropdown Logic
    const waterTypeSelect = document.getElementById('water-type');
    if (waterTypeSelect) {
        waterTypeSelect.addEventListener('change', (e) => {
            const recoveryInput = document.getElementById('recovery');
            if (e.target.value) {
                recoveryInput.value = e.target.value;
                validatePhysicalParameters();
                if (typeof calculateChemistry === 'function') {
                    calculateChemistry(false);
                }
            }
        });
    }

    // Setup Unit Radio Event Listeners
    document.querySelectorAll('input[name="flow-unit"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            const newUnit = e.target.value;
            const input = document.getElementById('flow');
            const val = parseFloat(input.value);
            if (!isNaN(val)) {
                const baseVal = conversions.flow.toBase(val, currentUnits.flow);
                const newVal = conversions.flow.fromBase(baseVal, newUnit);
                input.value = newVal.toFixed(1);
            }
            
            // Convert dec-q0
            const q0Input = document.getElementById('dec-q0');
            if (q0Input) {
                const q0Val = parseFloat(q0Input.value);
                if (!isNaN(q0Val)) {
                    const baseQ0 = conversions.flow.toBase(q0Val, currentUnits.flow);
                    const newQ0 = conversions.flow.fromBase(baseQ0, newUnit);
                    q0Input.value = newQ0.toFixed(1);
                }
            }
            
            // Convert regression table NPF entries
            document.querySelectorAll('.reg-npf').forEach(regInput => {
                const regVal = parseFloat(regInput.value);
                if (!isNaN(regVal)) {
                    const baseReg = conversions.flow.toBase(regVal, currentUnits.flow);
                    const newReg = conversions.flow.fromBase(baseReg, newUnit);
                    regInput.value = newReg.toFixed(2);
                }
            });
            
            currentUnits.flow = newUnit;
            
            // Update label beside input box
            const labelMap = { 'm3/h': 'm³/h', 'm3/d': 'm³/d', 'gpm': 'gpm', 'gpd': 'gpd' };
            document.getElementById('flow-unit-label').textContent = labelMap[newUnit];
            
            validatePhysicalParameters();
            // Removed auto-calculation: calculateChemistry(false);
            syncDeclineUnits();
            // Removed auto-calculation: runDeclineProjection();
        });
    });

    // Setup File Menu Toggling
    const fileMenuBtn = document.getElementById('file-menu-btn');
    const fileDropdownMenu = document.getElementById('file-dropdown-menu');

    if (fileMenuBtn && fileDropdownMenu) {
        fileMenuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = fileDropdownMenu.style.display === 'block';
            fileDropdownMenu.style.display = isOpen ? 'none' : 'block';
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!fileDropdownMenu.contains(e.target) && e.target !== fileMenuBtn) {
                fileDropdownMenu.style.display = 'none';
            }
        });
    }

    // Setup Feed Data View selector tab toggler and interactive switcher
    const tabButtons = {
        'file-tab-btn': { viewId: 'file-panel-view' },
        'project-details-tab-btn': { viewId: 'project-details-panel-view' },
        'feed-data-tab-btn': { viewId: 'feed-dashboard-view' },
        'calculation-tab-btn': { viewId: 'calculation-panel-view' },
        'scaling-tab-btn': { viewId: 'scaling-panel-view' },
        'process-tab-btn': { viewId: 'process-dashboard-view' },
        'aging-tab-btn': { viewId: 'aging-panel-view' },
        'report-tab-btn': { viewId: 'report-panel-view' }
    };

    const views = Object.values(tabButtons).map(info => document.getElementById(info.viewId)).filter(Boolean);
    const placeholderView = document.getElementById('tab-placeholder-view');

    Object.keys(tabButtons).forEach(id => {
        const btn = document.getElementById(id);
        if (btn) {
            btn.addEventListener('click', (e) => {
                if (btn.classList.contains('pace-locked-tab')) {
                    const toast = document.getElementById('pace-lock-toast');
                    if (toast) {
                        toast.style.display = 'flex';
                        setTimeout(() => { toast.style.display = 'none'; }, 3000);
                    }
                    return; // PREVENT TAB SWITCH
                }

                // Set active class
                document.querySelectorAll('.menu-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                localStorage.setItem('activeTabId', id);

                // Show "Run Analysis" button only on Feed Data tab
                const runAnalysisBtn = document.getElementById('run-analysis-btn');
                if (runAnalysisBtn) {
                    runAnalysisBtn.style.display = (id === 'feed-data-tab-btn') ? 'block' : 'none';
                }

                // Hide all views
                views.forEach(v => { if(v) v.style.display = 'none'; });
                if (placeholderView) placeholderView.style.display = 'none';

                // Show selected view
                const viewId = tabButtons[id].viewId;
                const view = document.getElementById(viewId);
                if (view) {
                    if (viewId === 'project-details-panel-view' || viewId === 'file-panel-view' || viewId === 'feed-dashboard-view' || viewId === 'report-panel-view') {
                        view.style.display = 'flex';
                        view.style.flexDirection = 'column';
                    } else {
                        view.style.display = 'grid';
                    }
                } else if (placeholderView) {
                    placeholderView.style.display = 'flex';
                }

                // specific tab logic
                if (id === 'aging-tab-btn') {
                    if(typeof syncAllParametersFromFeed === 'function') syncAllParametersFromFeed();
                } else if (id === 'calculation-tab-btn') {
                    if (typeof window.updateLivePFD === 'function') window.updateLivePFD();
                    
                    fetch(API_BASE + '/api/membranes')
                        .then(res => res.json())
                        .then(data => {
                            if(data.ro_membranes) {
                                if (!window.roMembranes) window.roMembranes = {};
                                data.ro_membranes.forEach(m => {
                                    if (!window.roMembranes[m.id]) window.roMembranes[m.id] = {};
                                    window.roMembranes[m.id].active_area_m2 = m.area;
                                    window.roMembranes[m.id].manufacturer = m.manufacturer;
                                    window.roMembranes[m.id].type = m.type;
                                });

                                const permionicsMems = data.ro_membranes.filter(m => m.manufacturer && m.manufacturer.toLowerCase() === 'permionics');
                                const roOptions = permionicsMems.map(m => `<option value="${m.id}">${m.name} (${m.type})</option>`).join('');
                                
                                const roSel = document.getElementById('calc-ro-membrane');
                                if(roSel) roSel.innerHTML = roOptions;
                                
                                const p2Sel = document.getElementById('calc-p2-membrane');
                                if(p2Sel) p2Sel.innerHTML = roOptions;
                            }
                            if(data.uf_modules) {
                                const ufSel = document.getElementById('calc-uf-module');
                                if(ufSel) ufSel.innerHTML = data.uf_modules.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
                            }
                        })
                        .catch(err => console.error('Failed to load membrane DB', err));
                } else if (id === 'report-tab-btn') {
                    if (typeof generateReportContent === 'function') generateReportContent();
                }
            });
        }
    });


    document.querySelectorAll('input[name="temp-unit"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            const newUnit = e.target.value;
            
            // 1. Convert Feed temp input
            const input = document.getElementById('temp');
            const val = parseFloat(input.value);
            if (!isNaN(val)) {
                const baseVal = conversions.temp.toBase(val, currentUnits.temp);
                const newVal = conversions.temp.fromBase(baseVal, newUnit);
                input.value = newVal.toFixed(1);
            }
            
            // 2. Convert dec-tref
            const trefInput = document.getElementById('dec-tref');
            if (trefInput) {
                const trefVal = parseFloat(trefInput.value);
                if (!isNaN(trefVal)) {
                    const baseTref = conversions.temp.toBase(trefVal, currentUnits.temp);
                    const newTref = conversions.temp.fromBase(baseTref, newUnit);
                    trefInput.value = newTref.toFixed(1);
                }
            }
            
            // 3. Convert dec-tact
            const tactInput = document.getElementById('dec-tact');
            if (tactInput) {
                const tactVal = parseFloat(tactInput.value);
                if (!isNaN(tactVal)) {
                    const baseTact = conversions.temp.toBase(tactVal, currentUnits.temp);
                    const newTact = conversions.temp.fromBase(baseTact, newUnit);
                    tactInput.value = newTact.toFixed(1);
                }
            }

            currentUnits.temp = newUnit;
            
            // Update label beside input box
            document.getElementById('temp-unit-label').textContent = newUnit === 'C' ? '°C' : '°F';
            
            validatePhysicalParameters();
            // Removed auto-calculation: calculateChemistry(false);
            syncDeclineUnits();
            // Removed auto-calculation: runDeclineProjection();
        });
    });

    document.querySelectorAll('input[name="pressure-unit"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            const newUnit = e.target.value;
            
            // Convert pressure values in Decline panel:
            // 1. dec-p0
            const p0Input = document.getElementById('dec-p0');
            if (p0Input) {
                const p0Val = parseFloat(p0Input.value);
                if (!isNaN(p0Val)) {
                    const baseP0 = conversions.pressure.toBase(p0Val, currentUnits.pressure);
                    const newP0 = conversions.pressure.fromBase(baseP0, newUnit);
                    p0Input.value = newP0.toFixed(1);
                }
            }
            
            // 2. dec-pback
            const pbackInput = document.getElementById('dec-pback');
            if (pbackInput) {
                const pbackVal = parseFloat(pbackInput.value);
                if (!isNaN(pbackVal)) {
                    const basePback = conversions.pressure.toBase(pbackVal, currentUnits.pressure);
                    const newPback = conversions.pressure.fromBase(basePback, newUnit);
                    pbackInput.value = newPback.toFixed(2);
                }
            }
            
            // 3. dec-deltap
            const deltapInput = document.getElementById('dec-deltap');
            if (deltapInput) {
                const deltapVal = parseFloat(deltapInput.value);
                if (!isNaN(deltapVal)) {
                    const baseDeltap = conversions.pressure.toBase(deltapVal, currentUnits.pressure);
                    const newDeltap = conversions.pressure.fromBase(baseDeltap, newUnit);
                    deltapInput.value = newDeltap.toFixed(2);
                }
            }

            currentUnits.pressure = newUnit;
            document.getElementById('pressure-unit-label').textContent = newUnit;
            
            validatePhysicalParameters();
            // Removed auto-calculation: calculateChemistry(true);
            syncDeclineUnits();
            // Removed auto-calculation: runDeclineProjection();
        });
    });

    document.querySelectorAll('input[name="flux-unit"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            currentUnits.flux = e.target.value;
        });
    });

    // Initial calculation (do not show results card until user explicitly runs it)
    calculateChemistry(false);
    
    // Restore active tab from localStorage to prevent resetting on page refresh
    let savedTabId = localStorage.getItem('activeTabId') || 'feed-data-tab-btn';
    let savedBtn = document.getElementById(savedTabId);

    // Initial validation to set lock states
    if (typeof window.validateProjectModal === 'function') {
        window.validateProjectModal();
    }
    
    // If the saved tab is locked, force fallback to project-details-tab-btn
    if (savedBtn && savedBtn.classList.contains('pace-locked-tab')) {
        savedTabId = 'project-details-tab-btn';
        savedBtn = document.getElementById(savedTabId);
    }
    
    if (savedBtn) {
        savedBtn.click();
    } else {
        document.getElementById('project-details-tab-btn').click();
    }

    // PHREEQC Integration
    const runPhreeqcBtn = document.getElementById('run-phreeqc-btn');
    if (runPhreeqcBtn) {
        runPhreeqcBtn.addEventListener('click', runPhreeqcCalculation);
    }
});

async function runPhreeqcCalculation() {
    const btn = document.getElementById('run-phreeqc-btn');
    
    // Extract current feed data
    const temp = parseFloat(document.getElementById('temp').value) || 25;
    const ph = parseFloat(document.getElementById('ph').value) || 7;
    const calcium = (parseFloat(document.getElementById('ca').value) || 0);
    const magnesium = (parseFloat(document.getElementById('mg').value) || 0);
    const sodium = (parseFloat(document.getElementById('na').value) || 0);
    const ca = (parseFloat(document.getElementById('ca').value) || 0);
    const mg = (parseFloat(document.getElementById('mg').value) || 0);
    const na = (parseFloat(document.getElementById('na').value) || 0);
    const cl = (parseFloat(document.getElementById('cl').value) || 0);
    const so4 = (parseFloat(document.getElementById('so4').value) || 0);
    const hco3 = (parseFloat(document.getElementById('hco3').value) || 0);
    const strontium = parseFloat(document.getElementById('sr').value) || 0;
    const fluoride = parseFloat(document.getElementById('f').value) || 0;
    const silica = parseFloat(document.getElementById('sio2').value) || 0;
    const barium = parseFloat(document.getElementById('ba').value) || 0;
    
    // Additional ions for accurate ionic strength
    const potassium = parseFloat(document.getElementById('k').value) || 0;
    const ammonium = parseFloat(document.getElementById('nh4').value) || 0;
    const carbonate = parseFloat(document.getElementById('co3').value) || 0;
    const nitrate = parseFloat(document.getElementById('no3').value) || 0;
    const aluminium = parseFloat((document.getElementById('al') || {}).value) || 0;
    const iron = parseFloat(document.getElementById('fe').value) || 0;
    const manganese = parseFloat(document.getElementById('mn').value) || 0;
    const phosphate = parseFloat(document.getElementById('po4').value) || 0;
    
    const payload = {
        temperature: temp,
        ph: ph,
        calcium: ca,
        magnesium: mg,
        sodium: na,
        chloride: cl,
        sulfate: so4,
        bicarbonate: hco3,
        strontium: strontium,
        fluoride: fluoride,
        silica: silica,
        barium: barium,
        potassium: potassium,
        ammonium: ammonium,
        carbonate: carbonate,
        nitrate: nitrate,
        aluminium: aluminium,
        iron: iron,
        manganese: manganese,
        phosphate: phosphate
    };

    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Calculating...';

        const response = await fetch(API_BASE + '/api/calculate-scaling', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        
        // Format helper to include % Saturation
        const formatSi = (val) => {
            if (val === null || val === undefined) return '--';
            if (val <= -99.00) return '--'; // Only mask mathematically impossible/extreme null values
            const pct = Math.pow(10, val) * 100;
            return `${val.toFixed(3)} (${pct.toFixed(0)}%)`;
        };
        
        // Update UI
        document.getElementById('si-gypsum').textContent = formatSi(result.gypsum_si);
        document.getElementById('si-anhydrite').textContent = formatSi(result.anhydrite_si);
        document.getElementById('si-calcite').textContent = formatSi(result.calcite_si);
        document.getElementById('si-barite').textContent = formatSi(result.barite_si);
        document.getElementById('si-srso4').textContent = formatSi(result.celestite_si);
        document.getElementById('si-caf2').textContent = formatSi(result.fluorite_si);
        document.getElementById('si-silica').textContent = formatSi(result.silica_si);
        document.getElementById('si-fe').textContent = formatSi(result.iron_si);
        document.getElementById('si-al').textContent = formatSi(result.aluminium_si);
        document.getElementById('si-mn').textContent = formatSi(result.manganese_si);
        document.getElementById('si-po4').textContent = formatSi(result.calcium_phosphate_si);
        

        
        // Color code based on saturation risk
        updateSiColor('si-gypsum', result.gypsum_si, 0);
        updateSiColor('si-anhydrite', result.anhydrite_si, 0);
        updateSiColor('si-calcite', result.calcite_si, 0);
        updateSiColor('si-barite', result.barite_si, 0);
        updateSiColor('si-srso4', result.celestite_si, 0);
        updateSiColor('si-caf2', result.fluorite_si, 0);
        updateSiColor('si-silica', result.silica_si, 0);
        updateSiColor('si-fe', result.iron_si, 0);
        updateSiColor('si-al', result.aluminium_si, 0);
        updateSiColor('si-mn', result.manganese_si, 0);
        updateSiColor('si-po4', result.calcium_phosphate_si, 0);


        // Update Chart
        if (window.siChart) {
            const rawData = [
                result.calcite_si, result.gypsum_si, result.silica_si, 
                result.iron_si, result.aluminium_si, result.manganese_si, result.calcium_phosphate_si,
                result.anhydrite_si, result.barite_si, result.celestite_si, result.fluorite_si
            ];

            // Filter out missing/extreme values so they don't crush the Y-axis scale
            window.siChart.data.datasets[0].data = rawData.map(val => (val <= -99.0) ? null : val);
            
            // Dynamic coloring (vibrant red if > 0, else purple/indigo to match final_UI)
            window.siChart.data.datasets[0].backgroundColor = window.siChart.data.datasets[0].data.map(val => {
                if (val === null) return 'rgba(0,0,0,0)';
                return val > 0 ? 'rgba(239, 68, 68, 0.85)' : 'rgba(79, 70, 229, 0.85)';
            });
            window.siChart.data.datasets[0].borderColor = window.siChart.data.datasets[0].data.map(val => {
                if (val === null) return 'rgba(0,0,0,0)';
                return val > 0 ? 'rgba(239, 68, 68, 1)' : 'rgba(79, 70, 229, 1)';
            });
            window.siChart.data.datasets[0].borderWidth = 2;
            window.siChart.data.datasets[0].borderRadius = 6;
            window.siChart.data.datasets[0].borderSkipped = false;
            window.siChart.update();
        }

    } catch (error) {
        console.error('PHREEQC API Error:', error);
        alert('Error: Could not connect to the Python backend. Is it running?');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-bolt"></i> Run Scaling Analysis';
    }
}

async function fetchProcessRecommendation() {
    const btn = document.getElementById('run-process-btn');
    
    // Extract feed data and design intent
    const payload = {
        feed_tds: parseFloat(document.getElementById('rep-tds') ? document.getElementById('rep-tds').textContent : 0) || 0,
        target_tds: parseFloat(document.getElementById('target-tds') ? document.getElementById('target-tds').value : 50) || 50,
        target_recovery: parseFloat(document.getElementById('recovery').value) || 75,
        feed_ph: parseFloat(document.getElementById('ph').value) || null,
        feed_temp: parseFloat(document.getElementById('temp').value) || null,
        
        sdi_15: parseFloat(document.getElementById('sdi').value) || null,
        turbidity: parseFloat(document.getElementById('turbidity').value) || null,
        toc: parseFloat(document.getElementById('toc').value) || null,
        iron_total: parseFloat(document.getElementById('fe').value) || null,
        manganese: parseFloat(document.getElementById('mn').value) || null,
        free_cl2: parseFloat(document.getElementById('cl2').value) || null,
        oil_grease: parseFloat(document.getElementById('oil-grease').value) || null,
        cod: parseFloat(document.getElementById('cod').value) || null,
        bod: parseFloat(document.getElementById('bod').value) || null,
        
        ca: parseFloat(document.getElementById('ca').value) || 0,
        mg_ion: parseFloat(document.getElementById('mg').value) || 0,
        na: parseFloat(document.getElementById('na').value) || 0,
        cl: parseFloat(document.getElementById('cl').value) || 0,
        so4: parseFloat(document.getElementById('so4').value) || 0,
        hco3: parseFloat(document.getElementById('hco3').value) || 0,
        k: parseFloat(document.getElementById('k').value) || 0,
        ba: parseFloat(document.getElementById('ba').value) || 0,
        sr: parseFloat(document.getElementById('sr').value) || 0,
        f: parseFloat(document.getElementById('f').value) || 0,
        sio2: parseFloat(document.getElementById('sio2').value) || 0,
        
        application: document.getElementById('application-type').value
    };

    // calculate basic TDS if not already done
    if (!payload.feed_tds) {
        const alVal = parseFloat((document.getElementById('al') || {}).value) || 0;
        const feVal = parseFloat(document.getElementById('fe').value) || 0;
        const mnVal = parseFloat(document.getElementById('mn').value) || 0;
        const co3Val = parseFloat(document.getElementById('co3').value) || 0;
        const no3Val = parseFloat(document.getElementById('no3').value) || 0;
        const po4Val = parseFloat(document.getElementById('po4').value) || 0;
        const nh4Val = parseFloat(document.getElementById('nh4').value) || 0;
        payload.feed_tds = payload.ca + payload.mg_ion + payload.na + payload.k + payload.ba + payload.sr + payload.cl + payload.so4 + payload.hco3 + payload.f + co3Val + no3Val + po4Val + nh4Val + alVal + feVal + mnVal;
    }
    
    // Attempt to map water type dropdown to source_type
    const wt = document.getElementById('water-type');
    const selectedOpt = wt.options[wt.selectedIndex];
    if (selectedOpt) {
        payload.source_type = selectedOpt.getAttribute('data-source-type') || "LOW_TDS";
    } else {
        payload.source_type = "LOW_TDS";
    }

    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Processing...';
        
        const response = await fetch(API_BASE + '/api/process-recommendation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const result = await response.json();
        
        // Update UI Dashboard
        document.getElementById('process-primary-config').textContent = result.primary_config || "N/A";
        document.getElementById('process-ro-variant').textContent = result.ro_variant || "Standard";
        document.getElementById('process-alternate-config').innerHTML = `<i class="fa-solid fa-code-branch"></i> Alternate: ${result.alternate_config || "None"}`;
        
        document.getElementById('process-confidence-score').textContent = result.confidence.score;
        document.getElementById('process-confidence-level').textContent = result.confidence.level;
        
        // Ring color logic
        const ring = document.getElementById('confidence-ring');
        let ringColor = 'var(--success-color)';
        if(result.confidence.score < 80) ringColor = 'var(--warning-color)';
        if(result.confidence.score < 55) ringColor = 'var(--error-color)';
        ring.style.background = `conic-gradient(${ringColor} ${result.confidence.score}%, rgba(255,255,255,0.1) 0%)`;
        document.getElementById('process-confidence-level').style.background = `rgba(${ringColor === 'var(--success-color)' ? '34,197,94' : (ringColor === 'var(--warning-color)' ? '245,158,11' : '239,68,68')}, 0.2)`;
        document.getElementById('process-confidence-level').style.color = ringColor;



        // 1. Run client-side pre-treatment first
        calculatePreTreatment(true);
        
        // 2. Append backend pre-treatment flags if any
        const preBox = document.getElementById('pretreatment-box');
        const preText = document.getElementById('pretreatment-text');
        
        if (result.pretreatment_flags && result.pretreatment_flags.length > 0) {
            preBox.style.display = 'block';
            const backendHtml = result.pretreatment_flags.map(flag => `
                <div class="pretreatment-step">
                    <i class="${getPretreatmentIcon(flag)}"></i>
                    <div>${flag}</div>
                </div>
            `).join('');
            preText.innerHTML = (preText.innerHTML || '') + backendHtml;
        }

        // 3. Build Process Flow Diagram
        const flowCard = document.getElementById('process-flow-card');
        const flowDiag = document.getElementById('process-flow-diagram');
        if (flowCard && flowDiag) {
            flowCard.style.display = 'block';
            let steps = [];
            
            // Step 1: Feed
            steps.push({
                icon: 'fa-solid fa-droplet',
                label: 'Feed Water',
                val: `${payload.feed_tds.toFixed(0)} mg/L`
            });
            
            // Step 2: Pre-treatment (if any flags or recommendations exist)
            const hasPre = (result.pretreatment_flags && result.pretreatment_flags.length > 0) || 
                          (preText && preText.innerHTML.trim() !== '');
            if (hasPre) {
                steps.push({
                    icon: 'fa-solid fa-filter',
                    label: 'Pre-treatment',
                    val: 'Required'
                });
            }
            
            // Step 3: UF (if uf_integration is true)
            if (result.uf_integration) {
                steps.push({
                    icon: 'fa-solid fa-shield-virus',
                    label: 'Ultrafiltration',
                    val: 'UF Membrane'
                });
            }
            
            // Step 4: Primary Pass
            let primVal = result.primary_config || 'RO';
            if (primVal.includes('UF+')) primVal = primVal.replace('UF+', '');
            steps.push({
                icon: 'fa-solid fa-network-wired',
                label: 'Primary Pass',
                val: primVal
            });
            
            // Step 5: Second Pass (if second pass is required)
            if (result.second_pass_required) {
                steps.push({
                    icon: 'fa-solid fa-forward',
                    label: 'Second Pass',
                    val: result.second_pass_high_ph ? 'High pH RO' : 'Standard RO'
                });
            }
            
            // Step 6: Permeate Product
            steps.push({
                icon: 'fa-solid fa-circle-check',
                label: 'Permeate',
                val: `< ${payload.target_tds} mg/L`
            });
            
            // Render steps joined by arrows
            const stepsHtml = steps.map((step, idx) => `
                <div class="flow-step">
                    <i class="${step.icon}"></i>
                    <span class="flow-step-label">${step.label}</span>
                    <span class="flow-step-val">${step.val}</span>
                </div>
            `).join(' <div class="flow-arrow"><i class="fa-solid fa-chevron-right"></i></div> ');
            
            flowDiag.innerHTML = stepsHtml;
        }

        // Render General Flags
        const flagContainer = document.getElementById('process-flags-container');
        flagContainer.innerHTML = '';
        
        const addFlagItem = (text) => {
            const div = document.createElement('div');
            div.style.padding = '0.8rem 1rem';
            div.style.marginBottom = '0.6rem';
            div.style.borderRadius = '6px';
            div.style.fontSize = '0.85rem';
            div.style.display = 'flex';
            div.style.alignItems = 'flex-start';
            div.style.gap = '0.6rem';
            
            div.style.background = 'rgba(59, 130, 246, 0.15)';
            div.style.border = '1px solid rgba(59, 130, 246, 0.3)';
            div.style.color = '#93c5fd';
            div.innerHTML = `<i class="fa-solid fa-circle-info" style="margin-top: 2px;"></i> <div>${text}</div>`;
            flagContainer.appendChild(div);
        };

        result.flags.forEach(f => addFlagItem(f));
        
        if(result.flags.length === 0) {
            flagContainer.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 2rem 0;">No significant engineering flags.</div>`;
        }

    } catch (error) {
        console.error('Process API Error:', error);
        alert('Error: Could not retrieve process recommendation.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-microchip"></i> Run Process Algorithm';
    }
}

async function fetchMembraneRecommendation() {
    const btn = document.getElementById('run-membrane-rec-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Processing...';
    }

    try {
        // Prepare inputs from existing feed data inputs
        const wt = document.getElementById('water-type');
        const selectedOpt = wt && wt.options && wt.selectedIndex !== -1 ? wt.options[wt.selectedIndex] : null;
        const source_type = selectedOpt ? (selectedOpt.getAttribute('data-source-type') || "LOW_TDS") : "LOW_TDS";

        // We no longer need the simple feed_tds summation because the calculation engine 
        // uses the complete feedData dictionary.
        const safeVal = (id) => {
            const el = document.getElementById(id);
            if (!el) return 0;
            return parseFloat(el.value || el.textContent) || 0;
        };

        const feedData = {
            calcium: safeVal('ca'),
            magnesium: safeVal('mg'),
            sodium: safeVal('na'),
            potassium: safeVal('k'),
            barium: safeVal('ba'),
            strontium: safeVal('sr'),
            chloride: safeVal('cl'),
            sulfate: safeVal('so4'),
            bicarbonate: safeVal('hco3'),
            nitrate: safeVal('no3'),
            fluoride: safeVal('f'),
            silica: safeVal('sio2'),
            boron: safeVal('b'),
            phosphate: safeVal('po4'),
            aluminium: safeVal('al'),
            iron: safeVal('fe'),
            manganese: safeVal('mn'),
            temperature: safeVal('temp') || 25,
            ph: safeVal('ph') || 7.5,
            tds: safeVal('calc-tds'),
            tss: safeVal('tss'),
            turbidity: safeVal('turbidity')
        };

        const vesselsEl = document.getElementById('calc-vessels-array');
        const vesselsStr = vesselsEl ? (vesselsEl.value || "4,2") : "4,2";
        const vessels = vesselsStr.split(',').map(s => parseInt(s.trim()) || 1);

        const safeInputVal = (id, fallback) => {
            const el = document.getElementById(id);
            if (!el || !el.value) return fallback;
            const val = parseFloat(el.value);
            return isNaN(val) ? fallback : val;
        };

        const payload = {
            technology_train: document.getElementById('calc-tech-train') ? document.getElementById('calc-tech-train').value : 'RO',
            feed_water: feedData,
            target_flow_m3h: safeInputVal('flow', 50.0),
            target_recovery_pct: document.getElementById('calc-target-recovery') ? safeInputVal('calc-target-recovery', 75.0) : safeInputVal('recovery', 75.0),
            target_tds: document.getElementById('target-tds') ? safeInputVal('target-tds', 50.0) : safeInputVal('rec-target-tds', 50.0),
            source_type: document.getElementById('water-type') && document.getElementById('water-type').selectedIndex !== -1 ? (document.getElementById('water-type').options[document.getElementById('water-type').selectedIndex].getAttribute('data-source-type') || 'LOW_TDS') : 'LOW_TDS',
            ro_membrane: 'placeholder',
            stages: safeInputVal('calc-stages', 2),
            vessels_per_stage: vessels,
            elements_per_vessel: safeInputVal('calc-elements-pv', 6)
        };

        const response = await fetch(API_BASE + '/api/recommend-membrane', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const result = await response.json();
        
        // Update best recommendation card
        const recommendations = result.recommendations || [];
        const bestModel = recommendations.length > 0 ? recommendations[0].model : null;
        
        const calcContainer = document.getElementById('calc-results-container') || document;
        const bestModelEl = calcContainer.querySelector('#membrane-best-model');
        const bestDescEl = calcContainer.querySelector('#membrane-best-desc');
        const bestTypeEl = calcContainer.querySelector('#membrane-best-type-badge');
        const bestScoreEl = calcContainer.querySelector('#membrane-best-score');
        const matchStatusEl = calcContainer.querySelector('#membrane-match-status');
        const scoreRingEl = calcContainer.querySelector('#membrane-score-ring');
        
        let bestScore = 0;
        let bestMatch = null;
        
        if (bestModel && recommendations.length > 0) {
            bestMatch = recommendations.find(r => r.model === bestModel);
            if (bestMatch) {
                bestScore = bestMatch.total_score;
                bestModelEl.textContent = bestMatch.model;
                bestDescEl.textContent = bestMatch.description || "Permionics Low-Fouling RO/NF Element";
                bestTypeEl.innerHTML = `<i class="fa-solid fa-layer-group"></i> Type: ${bestMatch.type} | Manufacturer: ${bestMatch.manufacturer}`;
                bestScoreEl.textContent = Math.round(bestScore);
            }
        } else {
            bestModelEl.textContent = "None";
            bestDescEl.textContent = "No suitable Permionics membrane matches the criteria or operating envelope.";
            bestTypeEl.innerHTML = `<i class="fa-solid fa-layer-group"></i> Type: N/A`;
            bestScoreEl.textContent = "--";
        }
        
        // Update match status badge and progress ring
        if (bestMatch) {
            matchStatusEl.textContent = bestScore >= 95 ? "EXCELLENT MATCH" : (bestScore >= 85 ? "GREAT MATCH" : (bestScore >= 75 ? "GOOD MATCH" : (bestScore >= 60 ? "FAIR MATCH" : "POOR MATCH")));
            matchStatusEl.className = bestScore >= 85 ? "feasibility-badge status-high" : (bestScore >= 60 ? "feasibility-badge status-medium" : "feasibility-badge status-low");
            
            // Set styles for status classes in JS inline to avoid styling issues
            if (bestScore >= 85) {
                matchStatusEl.style.backgroundColor = "rgba(34, 197, 94, 0.15)";
                matchStatusEl.style.color = "#4ade80";
                matchStatusEl.style.borderColor = "rgba(34, 197, 94, 0.3)";
                scoreRingEl.style.background = `conic-gradient(#22c55e ${bestScore}%, rgba(255,255,255,0.1) ${bestScore}%)`;
            } else if (bestScore >= 60) {
                matchStatusEl.style.backgroundColor = "rgba(245, 158, 11, 0.15)";
                matchStatusEl.style.color = "#fbbf24";
                matchStatusEl.style.borderColor = "rgba(245, 158, 11, 0.3)";
                scoreRingEl.style.background = `conic-gradient(#f59e0b ${bestScore}%, rgba(255,255,255,0.1) ${bestScore}%)`;
            } else {
                matchStatusEl.style.backgroundColor = "rgba(239, 68, 68, 0.15)";
                matchStatusEl.style.color = "#f87171";
                matchStatusEl.style.borderColor = "rgba(239, 68, 68, 0.3)";
                scoreRingEl.style.background = `conic-gradient(#ef4444 ${bestScore}%, rgba(255,255,255,0.1) ${bestScore}%)`;
            }
        } else {
            matchStatusEl.textContent = "INCOMPATIBLE";
            matchStatusEl.style.backgroundColor = "rgba(239, 68, 68, 0.15)";
            matchStatusEl.style.color = "#f87171";
            matchStatusEl.style.borderColor = "rgba(239, 68, 68, 0.3)";
            scoreRingEl.style.background = `conic-gradient(#ef4444 0%, rgba(255,255,255,0.1) 0%)`;
        }

        // Show/hide the apply button
        const applyBtn = calcContainer.querySelector('#apply-rec-btn');
        if (applyBtn) {
            applyBtn.style.display = bestMatch ? 'inline-block' : 'none';
        }

        // Store current recommendations globally for carousel navigation
        window.currentRecommendations = recommendations;
        window.currentRecommendationIndex = 0;
        window.lastBestModel = bestModel;

        // Populate active feed water details in the sidebar


        // Render all candidate membranes list
        const candidatesContainer = calcContainer.querySelector('#membrane-candidates-list');
        if (recommendations.length === 0) {
            candidatesContainer.innerHTML = `
                <div style="text-align: center; color: var(--text-secondary); padding: 3rem 0;">
                    <i class="fa-solid fa-circle-exclamation" style="font-size: 2.5rem; margin-bottom: 0.8rem; opacity: 0.3; color: var(--danger-color);"></i><br>
                    No Permionics membranes returned from the recommendation API.
                </div>
            `;
        } else {
            window.renderActiveRecommendation();
            document.getElementById('calc-results-container').style.display = 'flex';
            const loadingIndicator = document.getElementById('calc-loading-indicator');
            if (loadingIndicator) loadingIndicator.style.display = 'none';
            window.switchCalcSubTab('membrane');
        }

    } catch (error) {
        console.error('Membrane Rec API Error:', error);
        const calcContainer = document.getElementById('calc-results-container') || document;
        const candidatesContainer = calcContainer.querySelector('#membrane-candidates-list');
        if (candidatesContainer) {
            candidatesContainer.innerHTML = `
                <div style="text-align: center; color: var(--text-secondary); padding: 3rem 0;">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 2.5rem; margin-bottom: 0.8rem; color: var(--danger-color);"></i><br>
                    Failed to retrieve recommendations from the backend API.<br>
                    <small>${error.message}</small>
                </div>
            `;
        }
        document.getElementById('calc-results-container').style.display = 'flex';
        const loadingIndicator = document.getElementById('calc-loading-indicator');
        if (loadingIndicator) loadingIndicator.style.display = 'none';
        window.switchCalcSubTab('membrane');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-microchip"></i> Run Recommender';
        }
    }
}
// Expandable candidate cards toggler
window.toggleCandidateDetails = function(id) {
    const details = document.getElementById(id);
    if (details) {
        const isOpen = details.style.display === 'flex';
        details.style.display = isOpen ? 'none' : 'flex';
    }
};

window.fetchMembraneRecommendation = fetchMembraneRecommendation;

window.applyBestRecommendation = function() {
    if (window.lastBestModel) {
        const memSelect = document.getElementById('calc-ro-membrane');
        if (memSelect) {
            let exists = false;
            for(let i=0; i<memSelect.options.length; i++) {
                if(memSelect.options[i].value === window.lastBestModel) {
                    exists = true; break;
                }
            }
            if(!exists) {
                const opt = document.createElement('option');
                opt.value = window.lastBestModel;
                opt.text = "Permionics " + window.lastBestModel;
                memSelect.appendChild(opt);
            }
            memSelect.value = window.lastBestModel;
            // Update cached economic membrane cost with correct default to force recalculation with correct default
            const ecoMemCost = document.getElementById('eco-mem-cost');
            if (ecoMemCost) {
                let price = 26880.0;
                const model = window.lastBestModel;
                if (model) {
                    const lower = model.toLowerCase();
                    if (lower.includes('nf')) {
                        price = 19200.0;
                    } else if (window.roMembranes && window.roMembranes[model]) {
                        const mem = window.roMembranes[model];
                        if ((mem.type && mem.type.toUpperCase() === 'SWRO') || 
                            (mem.nominal_rejection !== undefined && mem.nominal_rejection >= 0.995) || 
                            (mem.rejection_pct !== undefined && mem.rejection_pct >= 0.995)) {
                            price = 30240.0;
                        }
                    } else if (lower.includes('swro') || lower.includes('sw30') || lower.includes('hpa-ro') || lower.includes('hparo') || lower.includes('hpa-4040')) {
                        price = 30240.0;
                    }
                }
                ecoMemCost.value = price;
            }
        }
        
        // Populate system array if backend returned estimated vessels
        const bestRec = window.currentRecommendations.find(r => r.model === window.lastBestModel);
        if (bestRec && bestRec.estimated_vessels) {
            const numStages = bestRec.estimated_vessels.length;
            const epv = parseInt(document.getElementById('calc-elements-pv').value) || 6;
            
            const stagesInput = document.getElementById('calc-stages');
            if (stagesInput) {
                stagesInput.value = numStages;
                stagesInput.dispatchEvent(new Event('input'));
            }
            
            const epvInput = document.getElementById('calc-elements-pv');
            if (epvInput) {
                epvInput.value = epv;
                epvInput.dispatchEvent(new Event('input'));
            }
            
            const vesselsArrayInput = document.getElementById('calc-vessels-array');
            if (vesselsArrayInput) {
                vesselsArrayInput.value = bestRec.estimated_vessels.join(', ');
                vesselsArrayInput.dispatchEvent(new Event('input'));
            }
        }
        
        // Switch back to calculation overview subtab
        window.switchCalcSubTab('overview');
    }
};

// Render active candidate membrane in carousel/slider view
window.renderActiveRecommendation = function() {
    const recommendations = window.currentRecommendations;
    const index = window.currentRecommendationIndex;
    const calcContainer = document.getElementById('calc-results-container') || document;
    const candidatesContainer = calcContainer.querySelector('#membrane-candidates-list');
    if (!recommendations || recommendations.length === 0) return;
    
    const rec = recommendations[index];
    const bestModel = window.lastBestModel || "";
    const isBest = rec.model === bestModel;
    const totalScore = rec.total_score;
    const isDQ = rec.is_disqualified;
    
    // Color indicators
    const scoreColor = isDQ ? "#ef4444" : (totalScore >= 85 ? "#22c55e" : (totalScore >= 60 ? "#f59e0b" : "#fb7185"));
    const matchClassText = isDQ ? "DISQUALIFIED" : (totalScore >= 95 ? "EXCELLENT" : (totalScore >= 85 ? "GREAT MATCH" : (totalScore >= 75 ? "GOOD MATCH" : (totalScore >= 60 ? "FAIR MATCH" : "POOR"))));
    const badgeColorBg = isDQ ? "rgba(239, 68, 68, 0.15)" : (totalScore >= 85 ? "rgba(34, 197, 94, 0.15)" : (totalScore >= 60 ? "rgba(245, 158, 11, 0.15)" : "rgba(251, 113, 133, 0.15)"));
    const badgeColorText = isDQ ? "#f87171" : (totalScore >= 85 ? "#4ade80" : (totalScore >= 60 ? "#fbbf24" : "#fda4af"));
    const badgeBorder = isDQ ? "rgba(239, 68, 68, 0.3)" : (totalScore >= 85 ? "rgba(34, 197, 94, 0.3)" : (totalScore >= 60 ? "rgba(245, 158, 11, 0.3)" : "rgba(251, 113, 133, 0.3)"));
    
    // Operating limits checklists
    const sdiLimitText = rec.is_disqualified && rec.disqualification_reason && rec.disqualification_reason.includes("SDI") ? 
        `<span style="color:#f87171"><i class="fa-solid fa-circle-xmark"></i> SDI Limit Exceeded</span>` : 
        `<span style="color:#4ade80"><i class="fa-solid fa-circle-check"></i> SDI within Limit</span>`;
    const tempLimitText = rec.is_disqualified && rec.disqualification_reason && rec.disqualification_reason.includes("temperature") ? 
        `<span style="color:#f87171"><i class="fa-solid fa-circle-xmark"></i> Temp Limit Exceeded</span>` : 
        `<span style="color:#4ade80"><i class="fa-solid fa-circle-check"></i> Temp within Limit</span>`;
    const phLimitText = rec.is_disqualified && rec.disqualification_reason && rec.disqualification_reason.includes("pH") ? 
        `<span style="color:#f87171"><i class="fa-solid fa-circle-xmark"></i> pH Limit Exceeded</span>` : 
        `<span style="color:#4ade80"><i class="fa-solid fa-circle-check"></i> pH within Limit</span>`;
    const chlorineLimitText = rec.is_disqualified && rec.disqualification_reason && rec.disqualification_reason.includes("chlorine") ? 
        `<span style="color:#f87171"><i class="fa-solid fa-circle-xmark"></i> Free Chlorine Exceeded</span>` : 
        `<span style="color:#4ade80"><i class="fa-solid fa-circle-check"></i> Chlorine within Limit</span>`;

    // Indicators dots html
    let dotsHtml = "";
    if (recommendations.length > 1) {
        dotsHtml = `
            <div style="display: flex; align-items: center; justify-content: center; gap: 0.5rem; margin-top: 1rem;">
                ${recommendations.map((r, i) => `
                    <div onclick="window.currentRecommendationIndex = ${i}; window.renderActiveRecommendation();" 
                         style="width: 8px; height: 8px; border-radius: 50%; background: ${i === index ? 'var(--accent-color)' : 'rgba(0,0,0,0.2)'}; 
                                cursor: pointer; transition: var(--transition);" 
                         title="${r.model}"></div>
                `).join('')}
            </div>
        `;
    }

    const navigationControls = recommendations.length > 1 ? `
        <button onclick="window.prevRecommendation();" class="carousel-nav-btn" style="background: rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.1); color: var(--text-color); border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: var(--transition);">
            <i class="fa-solid fa-chevron-left"></i>
        </button>
        <span style="font-size: 0.82rem; font-weight: 700; color: var(--text-secondary); min-width: 90px; text-align: center;">
            ${index + 1} of ${recommendations.length}
        </span>
        <button onclick="window.nextRecommendation();" class="carousel-nav-btn" style="background: rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.1); color: var(--text-color); border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: var(--transition);">
            <i class="fa-solid fa-chevron-right"></i>
        </button>
    ` : '';

    candidatesContainer.innerHTML = `
        <div class="carousel-outer" style="display: flex; flex-direction: column; gap: 0.6rem; width: 100%; position: relative; justify-content: space-between;">
            <div style="display: flex; align-items: stretch; gap: 0.6rem; width: 100%;">
                
                <!-- Slide Container with transitions -->
                <div class="carousel-slide-container" style="width: 100%; min-width: 0; transition: transform 0.3s ease, opacity 0.3s ease; opacity: 1; display: flex; flex-direction: column;" id="active-candidate-slide">
                    <div class="candidate-card ${isBest ? 'is-best' : ''}" style="box-sizing: border-box; width: 100%; background: linear-gradient(135deg, #1e40af, #3b82f6); border: 1px solid rgba(255, 255, 255, 0.15); box-shadow: 0 4px 20px rgba(30, 64, 175, 0.25); border-radius: 8px; padding: 1.2rem; display: flex; flex-direction: column;">
                        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                            <div style="display: flex; align-items: center; gap: 0.8rem;">
                                <div class="model-name" style="font-size: 1.3rem; font-weight: 800; color: #ffffff; font-family: 'Inter', sans-serif;">
                                    ${rec.model}
                                    ${isBest ? ' <span style="font-size:0.68rem; vertical-align:middle; background:rgba(255, 255, 255, 0.2); color:#ffffff; border:1px solid rgba(255,255,255,0.4); padding:0.1rem 0.4rem; border-radius:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; margin-left:0.4rem;">RECOMMENDED</span>' : ''}
                                </div>
                                <div class="meta-text" style="font-size: 0.78rem; color: #bfdbfe; font-weight: 500;">
                                    ${rec.manufacturer} | ${rec.type}
                                </div>
                            </div>
                            <div style="display: flex; align-items: center; gap: 0.8rem;">
                                <div style="font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: 12px; letter-spacing: 0.05em; border: 1px solid ${badgeBorder}; background: ${badgeColorBg}; color: ${badgeColorText};">
                                    ${matchClassText}
                                </div>
                            </div>
                        </div>
                        
                        <div class="metrics-text" style="font-size: 0.82rem; color: #bfdbfe; line-height: 1.35; border-left: 2px solid ${scoreColor}; padding-left: 0.7rem; margin: 0.8rem 0;">
                            Permeate TDS: <b style="color:#ffffff;">${rec.calculated_metrics.permeate_tds} mg/L</b> | Energy: <b style="color:#ffffff;">${rec.calculated_metrics.specific_energy} kWh/m³</b><br>
                            Feed Pressure: <b style="color:#ffffff;">${rec.calculated_metrics.feed_pressure_bar} bar</b> | Max CP (\u03B2): <b style="color:#ffffff;">${rec.max_beta ? rec.max_beta.toFixed(2) : '1.00'}</b>
                        </div>
                        
                        <!-- Details Panel -->
                        <div style="display: flex; flex-direction: column; gap: 0.7rem; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 0.7rem; margin-top: auto;">
                            <!-- DQ Banner if disqualified -->
                            ${isDQ ? `
                            <div style="background: rgba(239, 68, 68, 0.25); border: 1px solid rgba(239, 68, 68, 0.5); color: #fee2e2; padding: 0.6rem; border-radius: 4px; font-size: 0.82rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem;">
                                <i class="fa-solid fa-triangle-exclamation"></i> Disqualified: ${rec.disqualification_reason}
                            </div>
                            ` : ''}

                            <!-- Operating Envelope Limits Checklist -->
                            <div style="background: rgba(0,0,0,0.15); border-radius: 4px; padding: 0.4rem 0.7rem; border: 1px solid rgba(255,255,255,0.1);">
                                <h4 class="section-title" style="margin-top:0; margin-bottom:0.4rem; font-size:0.75rem; font-weight:700; color:#bfdbfe; text-transform:uppercase; letter-spacing:0.05em;">Criteria Scores</h4>
                                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.4rem; font-size:0.78rem;">
                                    <span style="color:#93c5fd"><i class="fa-solid fa-droplet"></i> Rejection: ${rec.criteria_scores.rejection || 0}/30</span>
                                    <span style="color:#93c5fd"><i class="fa-solid fa-bolt"></i> Energy: ${rec.criteria_scores.energy || 0}/30</span>
                                    <span style="color:#93c5fd"><i class="fa-solid fa-water"></i> Hydraulic: ${rec.criteria_scores.hydraulic || 0}/20</span>
                                    <span style="color:#93c5fd"><i class="fa-solid fa-gauge-high"></i> Envelope: ${rec.criteria_scores.envelope || 0}/20</span>
                                </div>
                            </div>

                            <!-- Evaluation Notes -->
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <h4 class="section-title" style="margin: 0; font-size:0.75rem; font-weight:700; color:#bfdbfe; text-transform:uppercase; letter-spacing:0.05em;">Engineering Notes</h4>
                                <ul class="notes-list" style="padding-left: 1rem; margin: 0; font-size: 0.78rem; color: #ffffff; line-height:1.45; display:flex; flex-direction:column; gap:0.15rem;">
                                    ${rec.justification && rec.justification.length > 0 ? rec.justification.map(note => `<li>${note}</li>`).join('') : '<li>No notes available.</li>'}
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
                
            </div>
            
            <!-- Bottom Controls (Chevrons + Dots) -->
            ${recommendations.length > 1 ? `
                <div style="display: flex; align-items: center; justify-content: space-between; padding-top: 0.5rem; margin-top: 0.5rem; width: 100%;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        ${navigationControls}
                    </div>
                    ${dotsHtml}
                </div>
            ` : ''}
        </div>
    `;

    // Add Swipe touch listeners to the active slide
    const slideEl = document.getElementById('active-candidate-slide');
    if (slideEl) {
        let startX = 0;
        let endX = 0;
        
        slideEl.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
        }, { passive: true });
        
        slideEl.addEventListener('touchend', (e) => {
            endX = e.changedTouches[0].clientX;
            const diff = startX - endX;
            if (Math.abs(diff) > 50) {
                if (diff > 0) {
                    window.nextRecommendation();
                } else {
                    window.prevRecommendation();
                }
            }
        }, { passive: true });
    }
};

window.prevRecommendation = function() {
    const recommendations = window.currentRecommendations;
    if (!recommendations || recommendations.length <= 1) return;
    
    const calcContainer = document.getElementById('calc-results-container') || document;
    const slide = calcContainer.querySelector('#active-candidate-slide');
    if (slide) {
        slide.style.transform = 'translateX(20px)';
        slide.style.opacity = '0';
    }
    
    setTimeout(() => {
        window.currentRecommendationIndex = (window.currentRecommendationIndex - 1 + recommendations.length) % recommendations.length;
        window.renderActiveRecommendation();
        
        const newSlide = calcContainer.querySelector('#active-candidate-slide');
        if (newSlide) {
            newSlide.style.transform = 'translateX(-20px)';
            newSlide.style.opacity = '0';
            newSlide.getBoundingClientRect();
            newSlide.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
            newSlide.style.transform = 'translateX(0)';
            newSlide.style.opacity = '1';
        }
    }, 150);
};

window.nextRecommendation = function() {
    const recommendations = window.currentRecommendations;
    if (!recommendations || recommendations.length <= 1) return;
    
    const calcContainer = document.getElementById('calc-results-container') || document;
    const slide = calcContainer.querySelector('#active-candidate-slide');
    if (slide) {
        slide.style.transform = 'translateX(-20px)';
        slide.style.opacity = '0';
    }
    
    setTimeout(() => {
        window.currentRecommendationIndex = (window.currentRecommendationIndex + 1) % recommendations.length;
        window.renderActiveRecommendation();
        
        const newSlide = calcContainer.querySelector('#active-candidate-slide');
        if (newSlide) {
            newSlide.style.transform = 'translateX(20px)';
            newSlide.style.opacity = '0';
            newSlide.getBoundingClientRect();
            newSlide.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
            newSlide.style.transform = 'translateX(0)';
            newSlide.style.opacity = '1';
        }
    }, 150);
};

function updateSiColor(elementId, value, threshold) {
    const el = document.getElementById(elementId);
    if (!el) return;
    if (value > threshold) {
        el.style.color = 'var(--error-color)'; // Red
        el.textContent += ' ⚠️';
    } else if (value > threshold - 0.5) {
        el.style.color = 'var(--warning-color)'; // Orange
    } else {
        el.style.color = 'var(--success-color)'; // Green
    }
}

function getVal(id) {
    const val = parseFloat(document.getElementById(id).value);
    return isNaN(val) ? 0 : val;
}

function setMsg(id, msg, type) {
    const el = document.getElementById(id);
    if(el) {
        el.textContent = msg;
        el.className = 'validation-message ' + (type === 'err' ? 'text-error' : type === 'warn' ? 'text-warning' : 'text-success');
    }
}

function validatePhysicalParameters() {
    let hasError = false;

    // pH validation
    const phInput = document.getElementById('ph');
    let ph = parseFloat(phInput.value);
    if (!isNaN(ph)) {
        if (ph <= 0) {
            phInput.value = 0.1;
            ph = 0.1;
            setMsg('msg-ph', 'Minimum pH is 0.1', 'err');
        } else if (ph > 14) {
            phInput.value = 14;
            ph = 14;
            setMsg('msg-ph', 'Maximum pH is 14', 'err');
        } else if (ph < 6.5 || ph > 8.5) {
            setMsg('msg-ph', 'Outside normal (6.5-8.5)', 'warn');
        } else {
            setMsg('msg-ph', 'OK', 'success');
        }
    }

    // Temp validation
    const rawTemp = parseFloat(document.getElementById('temp').value);
    if (!isNaN(rawTemp)) {
        const temp = conversions.temp.toBase(rawTemp, currentUnits.temp); // convert to base unit (°C) for validation
        if (temp < 0 || temp > 80) {
            setMsg('msg-temp', 'Invalid Temperature', 'warn');
        } else if (temp < 10 || temp > 40) {
            setMsg('msg-temp', `Outside 10-40°C`, 'warn');
        } else {
            setMsg('msg-temp', 'OK', 'success');
        }
    }

    // Recovery validation
    const recovery = parseFloat(document.getElementById('recovery').value);
    if (!isNaN(recovery)) {
        if (recovery <= 0 || recovery > 100) {
            setMsg('msg-recovery', 'Invalid recovery target', 'warn');
        } else if (recovery > 80) {
            setMsg('msg-recovery', 'High recovery (scaling risk)', 'warn');
        } else {
            setMsg('msg-recovery', 'OK', 'success');
        }
    }

    // Free Cl2 validation
    const cl2 = parseFloat(document.getElementById('cl2').value);
    if (!isNaN(cl2)) {
        if (cl2 > 0.1) {
            setMsg('msg-cl2', 'Dechlorination required', 'warn');
        } else {
            setMsg('msg-cl2', '', 'success');
        }
    }

    return hasError;
}

function calculateChemistry(showAllResults = false) {
    let sumCat = 0;
    let sumAn = 0;
    let ionicStrength = 0;
    let calculatedTds = 0;

    let totalCatMg = 0;
    let totalCatMeq = 0;
    let totalCatCaCO3 = 0;

    // Calculate Cations
    document.querySelectorAll('.cation').forEach(input => {
        const mgL = parseFloat(input.value) || 0;
        calculatedTds += mgL;
        totalCatMg += mgL;
        const mw = parseFloat(input.dataset.mw);
        const z = parseFloat(input.dataset.z);
        
        const meqL = (mgL * z) / mw;
        const caco3 = meqL * 50; // equivalent weight of CaCO3 is 50 g/eq
        
        totalCatMeq += meqL;
        totalCatCaCO3 += caco3;

        // Update row displays
        const meqEl = document.getElementById(`${input.id}-meq`);
        const caco3El = document.getElementById(`${input.id}-caco3`);
        if (meqEl) meqEl.textContent = mgL > 0 ? meqL.toFixed(4) : '—';
        if (caco3El) caco3El.textContent = mgL > 0 ? caco3.toFixed(2) : '—';

        const molL = mgL / (mw * 1000);
        sumCat += meqL;
        ionicStrength += 0.5 * (molL * Math.pow(z, 2));
    });

    let totalAnMg = 0;
    let totalAnMeq = 0;
    let totalAnCaCO3 = 0;

    // Calculate Anions
    document.querySelectorAll('.anion').forEach(input => {
        const mgL = parseFloat(input.value) || 0;
        calculatedTds += mgL;
        totalAnMg += mgL;
        const mw = parseFloat(input.dataset.mw);
        const z = parseFloat(input.dataset.z);
        
        const meqL = (mgL * z) / mw;
        const caco3 = meqL * 50;
        
        totalAnMeq += meqL;
        totalAnCaCO3 += caco3;

        // Update row displays
        const meqEl = document.getElementById(`${input.id}-meq`);
        const caco3El = document.getElementById(`${input.id}-caco3`);
        if (meqEl) meqEl.textContent = mgL > 0 ? meqL.toFixed(4) : '—';
        if (caco3El) caco3El.textContent = mgL > 0 ? caco3.toFixed(2) : '—';

        const molL = mgL / (mw * 1000);
        sumAn += meqL;
        ionicStrength += 0.5 * (molL * Math.pow(z, 2));
    });


    // Add additional fouling indicators that act as solutes (Aluminium, Iron, Manganese)
    const alVal = parseFloat((document.getElementById('al') || {}).value) || 0;
    const feVal = parseFloat(document.getElementById('fe').value) || 0;
    const mnVal = parseFloat(document.getElementById('mn').value) || 0;
    
    calculatedTds += alVal + feVal + mnVal;

    // Update Silica row displays (neutral species)
    const sio2MeqEl = document.getElementById('sio2-meq');
    const sio2Caco3El = document.getElementById('sio2-caco3');
    if (sio2MeqEl) sio2MeqEl.textContent = '0.0000';
    if (sio2Caco3El) sio2Caco3El.textContent = '0.00';

    // Update Table Totals Live (Including trace metals in mg/L total)
    const grandTotalMg = totalCatMg + totalAnMg + alVal + feVal + mnVal;
    const grandTotalMeq = totalCatMeq + totalAnMeq;
    const grandTotalCaCO3 = totalCatCaCO3 + totalAnCaCO3;

    document.getElementById('total-mgl').textContent = grandTotalMg.toFixed(2);
    document.getElementById('total-meq').textContent = grandTotalMeq.toFixed(4);
    document.getElementById('total-caco3').textContent = grandTotalCaCO3.toFixed(2);

    // Estimate Conductivity (TDS / 0.65 average ratio)
    let calcEc = calculatedTds / 0.65;

    // Osmotic Pressure Calculation: π = φ × R × T × ΣCi (mol/L)
    // R = 0.0831 L·bar/mol/K, T in Kelvin
    const R_gas = 0.0831;
    const rawTemp = parseFloat(document.getElementById('temp').value);
    const tempC = isNaN(rawTemp) ? 25 : conversions.temp.toBase(rawTemp, currentUnits.temp); // convert to standard Base Unit (°C)
    const T_kelvin = tempC + 273.15;

    // ΣCi in mol/L: sum of (mg/L) / (MW × 1000) for all ionic species
    let sumCi = 0;
    document.querySelectorAll('.cation, .anion').forEach(input => {
        const mgL = parseFloat(input.value) || 0;
        const mw = parseFloat(input.dataset.mw);
        if (!isNaN(mw) && mw > 0) {
            sumCi += mgL / (mw * 1000);
        }
    });

    // Add additional un-classed or neutral species to the solute molar sum
    const fe = parseFloat(document.getElementById('fe').value) || 0;
    const al = parseFloat((document.getElementById('al') || {}).value) || 0;
    const mn = parseFloat(document.getElementById('mn').value) || 0;
    const sio2Val = parseFloat(document.getElementById('sio2').value) || 0;

    sumCi += fe / (55.845 * 1000);  // Fe MW
    sumCi += al / (26.98 * 1000);   // Al MW
    sumCi += mn / (54.938 * 1000);  // Mn MW
    sumCi += sio2Val / (60.08 * 1000); // SiO2 MW

    // Get osmotic coefficient based on selected water type
    const phi = getOsmoticCoefficient();
    const osmoticPressureBase = phi * R_gas * T_kelvin * sumCi; // in bar
    window.lastCalculatedOsmoticPressure = osmoticPressureBase;
    const osmoticPressureDisplay = conversions.pressure.fromBase(osmoticPressureBase, currentUnits.pressure); // Convert to selected display unit

    // Render results based on state (live entering vs calculated)

    if (showAllResults) {
        document.getElementById('calc-tds').textContent = calculatedTds.toFixed(1);
        document.getElementById('calc-ec').textContent = calcEc.toFixed(1);
        document.getElementById('sum-cat').textContent = sumCat.toFixed(4);
        document.getElementById('sum-an').textContent = sumAn.toFixed(4);
        document.getElementById('osmotic-pressure').textContent = osmoticPressureDisplay.toFixed(2);
    } else {
        document.getElementById('calc-tds').textContent = '—';
        document.getElementById('calc-ec').textContent = '—';
        document.getElementById('sum-cat').textContent = '—';
        document.getElementById('sum-an').textContent = '—';
        document.getElementById('osmotic-pressure').textContent = '—';
    }

    const sumTotal = sumCat + sumAn;
    let cbe = 0;
    if (sumTotal > 0) {
        cbe = ((sumCat - sumAn) / sumTotal) * 100;
    }

    const cbeDisplay = document.getElementById('cbe-display');
    const cbeStatus = document.getElementById('cbe-status');
    const synBox = document.getElementById('synthetic-box');
    const synText = document.getElementById('synthetic-text');
    
    cbeDisplay.textContent = (cbe > 0 ? '+' : '') + cbe.toFixed(2) + '%';
    synBox.style.display = 'none';

    const absCbe = Math.abs(cbe);

    if (sumTotal === 0) {
        cbeStatus.textContent = 'NO DATA';
        cbeStatus.className = 'cbe-status';
    } else if (absCbe <= 5) {
        cbeStatus.textContent = 'ACCEPT';
        cbeStatus.className = 'cbe-status status-ok';
    } else if (absCbe <= 10) {
        cbeStatus.textContent = 'ACCEPT (WARNING)';
        cbeStatus.className = 'cbe-status status-warn';
    } else if (absCbe <= 15) {
        cbeStatus.textContent = 'LOW CONFIDENCE';
        cbeStatus.className = 'cbe-status status-warn';
        
        // Synthetic Balancing
        synBox.style.display = 'block';
        if (cbe > 0) {
            // Cation heavy -> Add Cl-
            const clToAddMeq = sumCat - sumAn;
            const clToAddMg = clToAddMeq * 35.45;
            synText.textContent = `Cation heavy. Suggest adding ${clToAddMg.toFixed(2)} mg/L of Cl⁻ for synthetic balance.`;
        } else {
            // Anion heavy -> Add Na+
            const naToAddMeq = sumAn - sumCat;
            const naToAddMg = naToAddMeq * 22.99;
            synText.textContent = `Anion heavy. Suggest adding ${naToAddMg.toFixed(2)} mg/L of Na⁺ for synthetic balance.`;
        }
    } else {
        cbeStatus.textContent = 'REJECTED';
        cbeStatus.className = 'cbe-status status-err';
    }

    calculatePreTreatment();
}

function getPretreatmentIcon(text) {
    const t = text.toLowerCase();
    if (t.includes('uf') || t.includes('ultrafiltration')) return 'fa-solid fa-filter';
    if (t.includes('dechlorination') || t.includes('smbs')) return 'fa-solid fa-droplet-slash';
    if (t.includes('iron') || t.includes('manganese') || t.includes('oxidation')) return 'fa-solid fa-flask';
    if (t.includes('cartridge')) return 'fa-solid fa-box-tissue';
    if (t.includes('biological') || t.includes('biofouling')) return 'fa-solid fa-biohazard';
    if (t.includes('oil') || t.includes('daf') || t.includes('grease')) return 'fa-solid fa-oil-can';
    if (t.includes('coagulation') || t.includes('flocculation') || t.includes('media filter')) return 'fa-solid fa-cubes';
    return 'fa-solid fa-circle-exclamation';
}

function calculatePreTreatment(showBox = false) {
    const sdiInput = document.getElementById('sdi');
    const sdiValue = sdiInput ? sdiInput.value.trim() : '';
    const hasSdi = sdiValue !== '';
    const sdi = hasSdi ? parseFloat(sdiValue) : NaN;
    
    const turbidity = getVal('turbidity');
    const fe = getVal('fe');
    const cl2 = getVal('cl2');
    
    const preBox = document.getElementById('pretreatment-box');
    const preText = document.getElementById('pretreatment-text');
    
    let recommendations = [];
    
    if (hasSdi && !isNaN(sdi)) {
        if (sdi > 5) {
            recommendations.push('Ultrafiltration (UF) + 5 μm cartridge filter (Mandatory)');
        } else if (sdi >= 3) {
            recommendations.push('Dual media filter + 5 μm cartridge filter');
        } else if (sdi > 0) {
            recommendations.push('5 μm cartridge filter only');
        }
    }
    
    if (turbidity > 1) {
        recommendations.push('Coagulation/Flocculation + Dual media filter');
    } else if (turbidity >= 0.5) {
        if (!recommendations.includes('Dual media filter + 5 μm cartridge filter')) {
            recommendations.push('Dual media filter + cartridge filter');
        }
    }

    if (fe > 0.05) {
        recommendations.push('Iron removal: Aeration or chlorination + media filtration + dechlorination');
    }

    if (cl2 > 0.1) {
        recommendations.push('SMBS dosing required for dechlorination');
    }

    if (recommendations.length > 0) {
        const html = recommendations.map(rec => `
            <div class="pretreatment-step">
                <i class="${getPretreatmentIcon(rec)}"></i>
                <div>${rec}</div>
            </div>
        `).join('');
        preText.innerHTML = html;
        if (showBox) {
            preBox.style.display = 'block';
        }
    } else {
        preText.innerHTML = '';
        if (showBox) {
            preBox.style.display = 'none';
        }
    }
}

function runFullValidation() {
    validatePhysicalParameters();
    calculateChemistry(true);
}

function getOsmoticCoefficient() {
    const select = document.getElementById('water-type');
    const selectedOption = select.options[select.selectedIndex];
    if (!selectedOption) return 0.93; // default brackish
    const sourceType = selectedOption.getAttribute('data-source-type') || '';

    const coefficients = {
        'WELL_WATER': 0.965,
        'LOW_TDS': 0.99,
        'BRACKISH_GW': 0.93,
        'SURFACE': 0.93,
        'SURFACE_SDI3': 0.93,
        'SEAWATER': 0.90,
        'SEAWATER_BEACH': 0.90,
        'WASTEWATER': 0.95,
        'WASTEWATER_UF': 0.95,
        'RO_PERMEATE': 0.99
    };
    return coefficients[sourceType] || 0.93;
}

// Sync Decline Panel Unit Labels dynamically
function syncDeclineUnits() {
    const flowLabel = { 'm3/h': 'm³/h', 'm3/d': 'm³/d', 'gpm': 'gpm', 'gpd': 'gpd' }[currentUnits.flow] || 'm³/h';
    const tempLabel = currentUnits.temp === 'C' ? '°C' : '°F';
    const pressLabel = currentUnits.pressure;
    
    // Update input unit labels
    if (document.getElementById('dec-p0-unit')) document.getElementById('dec-p0-unit').textContent = pressLabel;
    if (document.getElementById('dec-pback-unit')) document.getElementById('dec-pback-unit').textContent = pressLabel;
    if (document.getElementById('dec-deltap-unit')) document.getElementById('dec-deltap-unit').textContent = pressLabel;
    
    if (document.getElementById('dec-q0-unit')) document.getElementById('dec-q0-unit').textContent = flowLabel;
    
    if (document.getElementById('dec-tref-unit')) document.getElementById('dec-tref-unit').textContent = tempLabel;
    if (document.getElementById('dec-tact-unit')) document.getElementById('dec-tact-unit').textContent = tempLabel;
    
    // Update highlights row labels
    if (document.getElementById('dec-npf-unit-hl')) document.getElementById('dec-npf-unit-hl').textContent = flowLabel;
    if (document.getElementById('dec-osm-unit-hl')) document.getElementById('dec-osm-unit-hl').textContent = pressLabel;
    
    // Update table headers
    if (document.getElementById('dec-table-npf-unit')) document.getElementById('dec-table-npf-unit').textContent = flowLabel;
    if (document.getElementById('dec-table-q-unit')) document.getElementById('dec-table-q-unit').textContent = flowLabel;
    if (document.getElementById('dec-table-p-unit')) document.getElementById('dec-table-p-unit').textContent = pressLabel;
}

// Sync entered and calculated parameters from Feed Data section to Decline section
function syncAllParametersFromFeed() {
    // 0. Update Decline Panel Suffix Labels to match active Feed Data units
    syncDeclineUnits();
    
    // 1. Recovery Target -> dec-recovery
    const recovery = parseFloat(document.getElementById('recovery').value);
    if (!isNaN(recovery)) {
        document.getElementById('dec-recovery').value = recovery.toFixed(1);
    }
    
    // 2. Reference TDS -> dec-tdsref
    const calcTdsText = document.getElementById('calc-tds').textContent;
    const calcTds = parseFloat(calcTdsText);
    if (!isNaN(calcTds) && calcTdsText !== '—') {
        document.getElementById('dec-tdsref').value = Math.round(calcTds);
    } else {
        // If not calculated yet, sum up mg/L of all ions and additional solutes
        let sumMgL = 0;
        document.querySelectorAll('.cation, .anion, .neutral').forEach(input => {
            const val = parseFloat(input.value);
            if (!isNaN(val)) sumMgL += val;
        });
        sumMgL += (parseFloat((document.getElementById('al') || {}).value) || 0);
        sumMgL += (parseFloat(document.getElementById('fe').value) || 0);
        sumMgL += (parseFloat(document.getElementById('mn').value) || 0);
        if (sumMgL > 0) {
            document.getElementById('dec-tdsref').value = Math.round(sumMgL);
        }
    }
    
    // Initialize actual parameters on first sync/load to align default osmotic pressures
    if (!window.declineFirstSyncDone) {
        window.declineFirstSyncDone = true;
        
        const temp = parseFloat(document.getElementById('temp').value);
        if (!isNaN(temp)) {
            document.getElementById('dec-tact').value = temp.toFixed(1);
        }
        
        if (!isNaN(calcTds) && calcTdsText !== '—') {
            document.getElementById('dec-tdsact').value = Math.round(calcTds);
        } else {
            let sumMgL = 0;
            document.querySelectorAll('.cation, .anion, .neutral').forEach(input => {
                const val = parseFloat(input.value);
                if (!isNaN(val)) sumMgL += val;
            });
            sumMgL += (parseFloat((document.getElementById('al') || {}).value) || 0);
            sumMgL += (parseFloat(document.getElementById('fe').value) || 0);
            sumMgL += (parseFloat(document.getElementById('mn').value) || 0);
            if (sumMgL > 0) {
                document.getElementById('dec-tdsact').value = Math.round(sumMgL);
            }
        }
    }
    
    // 3. Osmotic Pressure -> dec-out-osm and local calculations
    syncOsmoticPressureFromFeed();
    
    // Sync calculated flow/pressure from calculations if available
    if (window.lastCalcResult && window.lastCalcResult.ro_results) {
        const roSum = window.lastCalcResult.ro_results.summary;
        if (roSum.perm_flow) {
            const q0Val = conversions.flow.fromBase(roSum.perm_flow, currentUnits.flow);
            document.getElementById('dec-q0').value = q0Val.toFixed(1);
        }
        if (roSum.feed_pressure_bar) {
            const p0Val = conversions.pressure.fromBase(roSum.feed_pressure_bar, currentUnits.pressure);
            document.getElementById('dec-p0').value = p0Val.toFixed(1);
        }
    }
    
    // Setup listeners on decline input changes so they auto-update in real-time
    setupDeclineRealtimeListeners();
    
    // Auto-run the projection on first switch or sync
    runDeclineProjection();
}

// Bind real-time change listeners to all decline inputs
function setupDeclineRealtimeListeners() {
    const declineInputs = [
        'dec-p0', 'dec-q0', 'dec-tref', 'dec-tdsref', 'dec-recovery',
        'dec-pback', 'dec-deltap', 'dec-tact', 'dec-tdsact', 'dec-horizon',
        'dec-rate-input'
    ];
    
    declineInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el && !el.dataset.listenerBound) {
            el.dataset.listenerBound = "true";
            el.addEventListener('input', () => {
                // Removed auto-calculation: runDeclineProjection();
            });
        }
    });
    
    const scenarioSelect = document.getElementById('dec-scenario');
    if (scenarioSelect && !scenarioSelect.dataset.listenerBound) {
        scenarioSelect.dataset.listenerBound = "true";
        scenarioSelect.addEventListener('change', () => {
            document.getElementById('dec-rate-input').value = scenarioSelect.value;
            // Removed auto-calculation: runDeclineProjection();
        });
    }
    
    document.querySelectorAll('input[name="decline-mode"]').forEach(radio => {
        if (!radio.dataset.listenerBound) {
            radio.dataset.listenerBound = "true";
            radio.addEventListener('change', () => {
                // Removed auto-calculation: runDeclineProjection();
            });
        }
    });
}

// Sync Osmotic Pressure from Feed Data section
function syncOsmoticPressureFromFeed() {
    const osmoticDisplayEl = document.getElementById('dec-out-osm');
    const tdsInput = document.getElementById('dec-tdsact');
    const recoveryInput = document.getElementById('dec-recovery');
    
    let pi_feed = 0;
    if (window.lastCalculatedOsmoticPressure && window.lastCalculatedOsmoticPressure > 0) {
        pi_feed = window.lastCalculatedOsmoticPressure;
    } else {
        const feedOsmoticText = document.getElementById('osmotic-pressure').textContent;
        const parsedVal = parseFloat(feedOsmoticText);
        if (!isNaN(parsedVal) && feedOsmoticText !== '—') {
            pi_feed = conversions.pressure.toBase(parsedVal, currentUnits.pressure);
        }
    }
    
    if (pi_feed > 0) {
        const pi_disp = conversions.pressure.fromBase(pi_feed, currentUnits.pressure);
        osmoticDisplayEl.textContent = pi_disp.toFixed(2);
        osmoticDisplayEl.style.color = 'var(--success-color)';
    } else {
        // Fallback Brackish estimate based on actual TDS
        const tds = parseFloat(tdsInput.value) || 2200;
        pi_feed = 0.7 * (tds / 1000);
        const pi_disp = conversions.pressure.fromBase(pi_feed, currentUnits.pressure);
        osmoticDisplayEl.textContent = pi_disp.toFixed(2) + ' (est)';
        osmoticDisplayEl.style.color = 'var(--warning-color)';
    }
    
    // Bind listeners once
    if (!window.declineListenersSetup) {
        window.declineListenersSetup = true;
        
        // Mode switching radios
        document.querySelectorAll('input[name="decline-mode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                const isDynamic = e.target.value === 'dynamic';
                document.getElementById('dec-standard-pane').style.display = isDynamic ? 'none' : 'block';
                document.getElementById('dec-dynamic-pane').style.display = isDynamic ? 'block' : 'none';
            });
        });
        
        // Standard scenario selection
        const scenarioSelect = document.getElementById('dec-scenario');
        if (scenarioSelect) {
            scenarioSelect.addEventListener('change', (e) => {
                document.getElementById('dec-rate-input').value = e.target.value;
            });
        }
    }
}

// Add regression table row
function addRegressionRow() {
    const tbody = document.getElementById('regression-tbody');
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="number" class="reg-month" value="" style="width: 100%; text-align: left; padding: 0.1rem 0.2rem;"></td>
        <td><input type="number" class="reg-npf" value="" step="0.01" style="width: 100%; padding: 0.1rem 0.2rem;"></td>
        <td><button type="button" class="btn" style="padding: 0.1rem 0.2rem; background: var(--error-color);" onclick="deleteRegRow(this)"><i class="fa-solid fa-trash"></i></button></td>
    `;
    tbody.appendChild(tr);
}

// Delete regression table row
function deleteRegRow(btn) {
    const row = btn.closest('tr');
    row.remove();
}

// Solve OLS Regression on natural log of monthly NPF input points over years
function solveRegression() {
    const rows = document.querySelectorAll('#regression-tbody tr');
    let points = [];
    
    rows.forEach(row => {
        const monthInput = row.querySelector('.reg-month');
        const npfInput = row.querySelector('.reg-npf');
        if (monthInput && npfInput) {
            const m = parseFloat(monthInput.value);
            const npf = parseFloat(npfInput.value);
            if (!isNaN(m) && !isNaN(npf) && npf > 0) {
                const npf_base = conversions.flow.toBase(npf, currentUnits.flow);
                points.push({ m: m, npf: npf_base });
            }
        }
    });
    
    if (points.length < 2) {
        alert("At least 2 valid historical NPF points are required to fit OLS regression.");
        return;
    }
    
    // Sort points by month
    points.sort((a, b) => a.m - b.m);
    
    // Fit y = ln(NPF) vs t = Month / 12
    let n = points.length;
    let sumT = 0;
    let sumY = 0;
    let sumT2 = 0;
    let sumTY = 0;
    
    let processedPoints = points.map(pt => {
        const t = pt.m / 12; // convert months to years
        const y = Math.log(pt.npf);
        sumT += t;
        sumY += y;
        sumT2 += t * t;
        sumTY += t * y;
        return { t, y };
    });
    
    const tMean = sumT / n;
    const yMean = sumY / n;
    
    let numerator = 0;
    let denominator = 0;
    
    processedPoints.forEach(pt => {
        numerator += (pt.t - tMean) * (pt.y - yMean);
        denominator += Math.pow(pt.t - tMean, 2);
    });
    
    if (denominator === 0) {
        alert("Invalid time axis. Month values must differ to fit a regression line.");
        return;
    }
    
    const slope = numerator / denominator;
    const intercept = yMean - slope * tMean;
    
    // Annualized degradation rate r = 1 - e^m
    const r_decimal = 1 - Math.exp(slope);
    const r_percent = r_decimal * 100;
    
    // R^2 goodness of fit
    let ssRes = 0;
    let ssTot = 0;
    processedPoints.forEach(pt => {
        const yPred = intercept + slope * pt.t;
        ssRes += Math.pow(pt.y - yPred, 2);
        ssTot += Math.pow(pt.y - yMean, 2);
    });
    
    const r2 = ssTot === 0 ? 1 : 1 - (ssRes / ssTot);
    
    // Populate outputs
    document.getElementById('dec-rate-input').value = r_percent.toFixed(2);
    document.getElementById('dec-out-rate').textContent = r_percent.toFixed(2) + '%';
    
    let r2_desc = "Poor fit";
    let colorClass = "var(--error-color)";
    if (r2 >= 0.95) { r2_desc = "Excellent fit"; colorClass = "var(--success-color)"; }
    else if (r2 >= 0.85) { r2_desc = "Good fit"; colorClass = "var(--success-color)"; }
    else if (r2 >= 0.70) { r2_desc = "Moderate fit"; colorClass = "var(--warning-color)"; }
    
    const r2Label = document.getElementById('dec-out-r2-label');
    r2Label.innerHTML = `<span style="color: ${colorClass}; font-weight: bold;">R²: ${r2.toFixed(4)}</span> (${r2_desc})`;
    
    alert(`OLS Regression Solved!\n---------------------\nAnnual Rate (r): ${r_percent.toFixed(2)}%/year\nGoodness of Fit (R²): ${r2.toFixed(4)} (${r2_desc})`);
}

// Run Year-by-Year Performance decline projections
function runDeclineProjection() {
    // Guard: only run if the decline projection elements exist on this page
    if (!document.getElementById('dec-p0')) return;
    // Inputs in user-preferred display units
    const p0 = parseFloat(document.getElementById('dec-p0').value) || 12.0;
    const q0 = parseFloat(document.getElementById('dec-q0').value) || 100.0;
    const tref = parseFloat(document.getElementById('dec-tref').value) || 25.0;
    const tdsref = parseFloat(document.getElementById('dec-tdsref').value) || 2000;
    const recovery = parseFloat(document.getElementById('dec-recovery').value) || 75.0;
    const pback = parseFloat(document.getElementById('dec-pback').value) || 0.5;
    const deltap = parseFloat(document.getElementById('dec-deltap').value) || 0.8;
    
    const tact = parseFloat(document.getElementById('dec-tact').value) || 30.0;
    const tdsact = parseFloat(document.getElementById('dec-tdsact').value) || 2200;
    const horizon = parseInt(document.getElementById('dec-horizon').value) || 5;
    const trigger = parseFloat(document.getElementById('dec-trigger').value) || 20.0;
    
    // Convert inputs to base metric system for consistent calculation (Flow: m3/h, Pressure: bar, Temp: °C)
    const p0_base = conversions.pressure.toBase(p0, currentUnits.pressure);
    const q0_base = conversions.flow.toBase(q0, currentUnits.flow);
    const tref_base = conversions.temp.toBase(tref, currentUnits.temp);
    const pback_base = conversions.pressure.toBase(pback, currentUnits.pressure);
    const deltap_base = conversions.pressure.toBase(deltap, currentUnits.pressure);
    
    const tact_base = conversions.temp.toBase(tact, currentUnits.temp);
    
    // Get annual rate r
    const rateInput = parseFloat(document.getElementById('dec-rate-input').value);
    if (isNaN(rateInput) || rateInput <= 0) {
        alert("Please enter a valid Annual Degradation Rate (> 0%).");
        return;
    }
    const r = rateInput / 100;
    
    // Recovery fraction
    const R_frac = recovery / 100;
    
    // Retrieve baseline osmotic pressure and TDS from Feed Data
    // Retrieve reference feed osmotic pressure from Feed Data section
    let pi_feed_ref = 0;
    if (window.lastCalculatedOsmoticPressure && window.lastCalculatedOsmoticPressure > 0) {
        pi_feed_ref = window.lastCalculatedOsmoticPressure;
    } else {
        const feedOsmoticText = document.getElementById('osmotic-pressure').textContent;
        const parsedVal = parseFloat(feedOsmoticText);
        if (!isNaN(parsedVal) && feedOsmoticText !== '—') {
            pi_feed_ref = conversions.pressure.toBase(parsedVal, currentUnits.pressure);
        }
    }
    
    // Fallback reference if feed data was never calculated
    if (pi_feed_ref <= 0) {
        pi_feed_ref = 0.7 * (tdsref / 1000);
    }
    
    // Only for calculating actual osmotic pressure use the 0.7 * TDS_act / 1000 formula
    const pi_feed_act = 0.7 * (tdsact / 1000);
    
    // Average Osmotic Pressures based on recovery target R fraction
    const conc_factor = (2 - R_frac) / (2 * (1 - R_frac));
    const pi_avg_ref = pi_feed_ref * conc_factor;
    const pi_avg_act = pi_feed_act * conc_factor;
    
    // Step 1: Temperature Correction Factor (TCF)
    const T_ref_K = tref_base + 273.15;
    const T_act_K = tact_base + 273.15;
    const U = tact_base < 25.0 ? 2640 : 3020;
    const TCF_ref = 1.0;
    const TCF_act = Math.exp(U * (1/T_ref_K - 1/T_act_K));
    
    // Step 3: NDP
    const NDP_ref = p0_base - deltap_base/2 - pback_base - pi_avg_ref;
    const NDP_act = p0_base - deltap_base/2 - pback_base - pi_avg_act;
    
    if (NDP_ref <= 0 || NDP_act <= 0) {
        const ndp_ref_disp = conversions.pressure.fromBase(NDP_ref, currentUnits.pressure);
        const ndp_act_disp = conversions.pressure.fromBase(NDP_act, currentUnits.pressure);
        const press_unit = currentUnits.pressure;
        
        // Render in the table body in red
        const tbody = document.getElementById('decline-results-tbody');
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; color: var(--error-color); padding: 1.5rem; font-weight: bold; font-size: 0.85rem;">
                    <i class="fa-solid fa-triangle-exclamation"></i> Error: Negative Net Driving Pressure (NDP ref: ${ndp_ref_disp.toFixed(2)} ${press_unit}, act: ${ndp_act_disp.toFixed(2)} ${press_unit}). Please increase feed operating pressure or reduce recovery/TDS targets.
                </td>
            </tr>
        `;
        
        // Render in the chart container as well
        document.getElementById('dec-chart-placeholder').innerHTML = `
            <i class="fa-solid fa-triangle-exclamation" style="font-size: 2.5rem; color: var(--error-color); margin-bottom: 0.5rem; display: block; opacity: 0.8;"></i>
            <span style="color: var(--error-color); font-weight: bold; font-size: 0.85rem;">Calculation Blocked: Negative Net Driving Pressure (NDP)</span>
        `;
        document.getElementById('dec-chart-placeholder').style.display = 'block';
        document.getElementById('dec-svg-chart-npf').style.display = 'none';
        document.getElementById('dec-svg-chart-press').style.display = 'none';
        
        // Clear out highlight panels
        document.getElementById('dec-out-npf').textContent = '—';
        document.getElementById('dec-out-repl-yr').textContent = 'Error';
        document.getElementById('dec-out-repl-yr').style.color = 'var(--error-color)';
        document.getElementById('dec-out-status-label').textContent = 'Negative NDP';
        document.getElementById('dec-out-status-label').style.color = 'var(--error-color)';
        return;
    }
    
    // Step 4: Baseline NPF (in base unit m3/h)
    const NPF_baseline = q0_base * (TCF_ref / TCF_act) * (NDP_ref / NDP_act);
    
    // Year-by-year projections loop
    let dataPoints = [];
    let firstReplYear = -1;
    
    for (let yr = 0; yr <= horizon; yr++) {
        // NPF decay (in base m3/h)
        const NPF_n = NPF_baseline * Math.pow(1 - r, yr);
        const NPF_drop = ((NPF_baseline - NPF_n) / NPF_baseline) * 100;
        
        // Actual flow decline under constant pressure (in base m3/h)
        const Q_act_n = q0_base * Math.pow(1 - r, yr);
        
        // Required Feed Pressure back-calculation (in base bar)
        const NDP_req_n = NDP_ref / Math.pow(1 - r, yr);
        const P_req_n = NDP_req_n + deltap_base/2 + pback_base + pi_avg_ref;
        
        // Convert back to user preferred display units
        const NPF_n_disp = conversions.flow.fromBase(NPF_n, currentUnits.flow);
        const Q_act_n_disp = conversions.flow.fromBase(Q_act_n, currentUnits.flow);
        const P_req_n_disp = conversions.pressure.fromBase(P_req_n, currentUnits.pressure);
        
        // Status logic
        let status = "NORMAL";
        if (NPF_drop >= trigger) {
            status = "REPLACE";
            if (firstReplYear === -1) firstReplYear = yr;
        } else if (NPF_drop >= 10.0) {
            status = "MONITOR";
        }
        
        dataPoints.push({
            year: yr,
            npf: NPF_n_disp,
            drop: NPF_drop,
            q_act: Q_act_n_disp,
            p_req: P_req_n_disp,
            status: status
        });
    }
    
    // Store globally for interactive hover crosshairs
    window.declineDataPoints = dataPoints;
    
    // Display results highlights in preferred display units
    const NPF_baseline_disp = conversions.flow.fromBase(NPF_baseline, currentUnits.flow);
    const pi_feed_ref_disp = conversions.pressure.fromBase(pi_feed_ref, currentUnits.pressure);
    
    document.getElementById('dec-out-npf').textContent = NPF_baseline_disp.toFixed(2);
    document.getElementById('dec-out-rate').textContent = (r * 100).toFixed(2) + '%';
    document.getElementById('dec-out-osm').textContent = pi_feed_ref_disp.toFixed(2);
    
    const replYrEl = document.getElementById('dec-out-repl-yr');
    const statusLabelEl = document.getElementById('dec-out-status-label');
    
    if (firstReplYear !== -1) {
        replYrEl.textContent = `Year ${firstReplYear}`;
        replYrEl.style.color = 'var(--error-color)';
        statusLabelEl.textContent = "Replacement Overdue";
        statusLabelEl.style.color = 'var(--error-color)';
    } else {
        replYrEl.textContent = 'Stable';
        replYrEl.style.color = 'var(--success-color)';
        statusLabelEl.textContent = "All Systems Nominal";
        statusLabelEl.style.color = 'var(--success-color)';
    }
    
    // Render outputs table
    const tbody = document.getElementById('decline-results-tbody');
    tbody.innerHTML = '';
    
    dataPoints.forEach(pt => {
        const tr = document.createElement('tr');
        if (pt.status === 'REPLACE') {
            tr.style.background = 'rgba(239, 68, 68, 0.15)';
        } else if (pt.status === 'MONITOR') {
            tr.style.background = 'rgba(245, 158, 11, 0.1)';
        }
        
        let badgeClass = "status-ok";
        if (pt.status === 'REPLACE') badgeClass = "status-err";
        else if (pt.status === 'MONITOR') badgeClass = "status-warn";
        
        tr.innerHTML = `
            <td>Year ${pt.year}</td>
            <td><span style="font-family: monospace;">${pt.npf.toFixed(2)}</span></td>
            <td><span style="font-family: monospace;">${pt.drop.toFixed(1)}%</span></td>
            <td><span style="font-family: monospace;">${pt.q_act.toFixed(1)}</span></td>
            <td><span style="font-family: monospace;">${pt.p_req.toFixed(2)}</span></td>
            <td><span class="cbe-status ${badgeClass}" style="font-size:0.65rem; padding:0.1rem 0.4rem;">${pt.status}</span></td>
        `;
        tbody.appendChild(tr);
    });
    
    // Draw SVG Performance Chart
    drawDeclineChart(dataPoints, trigger);
}

// Draw premium responsive interactive SVG charts (separate NPF and Pressure graphs with hover tooltip)
function drawDeclineChart(dataPoints, triggerThreshold) {
    const placeholder = document.getElementById('dec-chart-placeholder');
    const svgNpf = document.getElementById('dec-svg-chart-npf');
    const svgPress = document.getElementById('dec-svg-chart-press');
    
    if (dataPoints.length === 0) {
        placeholder.style.display = 'block';
        svgNpf.style.display = 'none';
        svgPress.style.display = 'none';
        return;
    }
    
    placeholder.style.display = 'none';
    svgNpf.style.display = 'block';
    svgPress.style.display = 'block';
    svgNpf.innerHTML = ''; 
    svgPress.innerHTML = '';
    
    // Create HTML tooltip dynamically inside chart container if missing
    let tooltip = document.getElementById('dec-chart-tooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'dec-chart-tooltip';
        tooltip.style.position = 'absolute';
        tooltip.style.display = 'none';
        tooltip.style.background = 'rgba(15, 23, 42, 0.95)';
        tooltip.style.border = '1px solid var(--accent-color)';
        tooltip.style.padding = '0.4rem 0.75rem';
        tooltip.style.borderRadius = '4px';
        tooltip.style.color = '#fff';
        tooltip.style.fontSize = '0.72rem';
        tooltip.style.fontFamily = 'Consolas, monospace';
        tooltip.style.pointerEvents = 'none';
        tooltip.style.boxShadow = '0 6px 16px rgba(0,0,0,0.6)';
        tooltip.style.zIndex = '200';
        tooltip.style.borderLeft = '3px solid var(--accent-color)';
        document.getElementById('dec-chart-container').appendChild(tooltip);
    }
    
    const horizon = dataPoints[dataPoints.length - 1].year;
    
    // --- Chart 1: NPF Decline Curve ---
    const w1 = svgNpf.clientWidth || 300;
    const h1 = svgNpf.clientHeight || 200;
    const pad1 = { top: 20, right: 15, bottom: 25, left: 35 };
    const gw1 = w1 - pad1.left - pad1.right;
    const gh1 = h1 - pad1.top - pad1.bottom;
    
    const npfMax = dataPoints[0].npf * 1.05;
    const npfMin = dataPoints[0].npf * 0.4;
    
    const getX1 = (yr) => pad1.left + (yr / horizon) * gw1;
    const getY1 = (val) => pad1.top + gh1 - ((val - npfMin) / (npfMax - npfMin)) * gh1;
    
    let contentNpf = '';
    
    // Gridlines & Ticks
    for (let yr = 0; yr <= horizon; yr++) {
        const x = getX1(yr);
        contentNpf += `
            <line x1="${x}" y1="${pad1.top}" x2="${x}" y2="${pad1.top + gh1}" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
            <text x="${x}" y="${pad1.top + gh1 + 14}" fill="var(--text-secondary)" font-size="8" text-anchor="middle">Yr ${yr}</text>
        `;
    }
    for (let i = 0; i <= 4; i++) {
        const val = npfMin + (i / 4) * (npfMax - npfMin);
        const y = getY1(val);
        contentNpf += `
            <line x1="${pad1.left}" y1="${y}" x2="${w1 - pad1.right}" y2="${y}" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
            <text x="${pad1.left - 6}" y="${y + 3}" fill="var(--text-secondary)" font-size="8" text-anchor="end">${val.toFixed(0)}</text>
        `;
    }
    
    // Invisible Crosshair line
    contentNpf += `<line id="dec-cross-npf" x1="0" y1="${pad1.top}" x2="0" y2="${pad1.top + gh1}" stroke="rgba(255,255,255,0.25)" stroke-dasharray="2,2" stroke-width="1" style="display:none;" />`;
    
    // Replacement Threshold Line
    const thresholdNpf = dataPoints[0].npf * (1 - triggerThreshold / 100);
    const thresholdY = getY1(thresholdNpf);
    contentNpf += `
        <line x1="${pad1.left}" y1="${thresholdY}" x2="${w1 - pad1.right}" y2="${thresholdY}" stroke="var(--error-color)" stroke-width="1.2" stroke-dasharray="3,3" />
        <text x="${w1 - pad1.right - 5}" y="${thresholdY - 4}" fill="var(--error-color)" font-size="7.5" font-weight="bold" text-anchor="end">Limit (${triggerThreshold}%)</text>
    `;
    
    // NPF Decline Curve
    let npfPath = '';
    dataPoints.forEach((pt, idx) => {
        const cmd = idx === 0 ? 'M' : 'L';
        npfPath += `${cmd} ${getX1(pt.year)} ${getY1(pt.npf)} `;
    });
    contentNpf += `<path d="${npfPath}" fill="none" stroke="var(--success-color)" stroke-width="2.2" />`;
    
    // NPF Markers
    dataPoints.forEach(pt => {
        contentNpf += `<circle id="marker-npf-${pt.year}" cx="${getX1(pt.year)}" cy="${getY1(pt.npf)}" r="3.5" fill="var(--success-color)" stroke="var(--card-bg)" stroke-width="1.2" style="transition: r 0.08s ease;" />`;
    });
    
    // Legend Title
    const flowLabel = { 'm3/h': 'm³/h', 'm3/d': 'm³/d', 'gpm': 'gpm', 'gpd': 'gpd' }[currentUnits.flow] || 'm³/h';
    contentNpf += `<text x="${pad1.left}" y="${pad1.top - 8}" fill="var(--success-color)" font-size="8.5" font-weight="bold" text-anchor="start">NPF DECLINE (${flowLabel})</text>`;
    
    // Invisible Interactive Hover Overlay Slices
    const sliceWidth1 = gw1 / horizon;
    for (let yr = 0; yr <= horizon; yr++) {
        const x = getX1(yr);
        contentNpf += `
            <rect x="${x - sliceWidth1/2}" y="${pad1.top}" width="${sliceWidth1}" height="${gh1}" fill="transparent" style="cursor: crosshair;"
                onmouseover="hoverDeclineData(${yr}, 'npf', event)"
                onmousemove="hoverDeclineData(${yr}, 'npf', event)"
                onmouseout="leaveDeclineData(${yr}, 'npf')" />
        `;
    }
    svgNpf.innerHTML = contentNpf;
    
    
    // --- Chart 2: Operating Pressure Escalation ---
    const w2 = svgPress.clientWidth || 300;
    const h2 = svgPress.clientHeight || 200;
    const pad2 = { top: 20, right: 15, bottom: 25, left: 35 };
    const gw2 = w2 - pad2.left - pad2.right;
    const gh2 = h2 - pad2.top - pad2.bottom;
    
    const pressValues = dataPoints.map(p => p.p_req);
    const pMax = Math.max(...pressValues) * 1.1;
    const pMin = Math.min(...pressValues) * 0.9;
    
    const getX2 = (yr) => pad2.left + (yr / horizon) * gw2;
    const getY2 = (val) => pad2.top + gh2 - ((val - pMin) / (pMax - pMin)) * gh2;
    
    let contentPress = '';
    // Gridlines & Ticks
    for (let yr = 0; yr <= horizon; yr++) {
        const x = getX2(yr);
        contentPress += `
            <line x1="${x}" y1="${pad2.top}" x2="${x}" y2="${pad2.top + gh2}" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
            <text x="${x}" y="${pad2.top + gh2 + 14}" fill="var(--text-secondary)" font-size="8" text-anchor="middle">Yr ${yr}</text>
        `;
    }
    for (let i = 0; i <= 4; i++) {
        const val = pMin + (i / 4) * (pMax - pMin);
        const y = getY2(val);
        contentPress += `
            <line x1="${pad2.left}" y1="${y}" x2="${w2 - pad2.right}" y2="${y}" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
            <text x="${pad2.left - 6}" y="${y + 3}" fill="var(--text-secondary)" font-size="8" text-anchor="end">${val.toFixed(1)}</text>
        `;
    }
    
    // Invisible Crosshair line
    contentPress += `<line id="dec-cross-press" x1="0" y1="${pad2.top}" x2="0" y2="${pad2.top + gh2}" stroke="rgba(255,255,255,0.25)" stroke-dasharray="2,2" stroke-width="1" style="display:none;" />`;
    
    // Pressure Curve
    let pressPath = '';
    dataPoints.forEach((pt, idx) => {
        const cmd = idx === 0 ? 'M' : 'L';
        pressPath += `${cmd} ${getX2(pt.year)} ${getY2(pt.p_req)} `;
    });
    contentPress += `<path d="${pressPath}" fill="none" stroke="#3b82f6" stroke-width="2.2" stroke-dasharray="1" />`;
    
    // Pressure Markers
    dataPoints.forEach(pt => {
        contentPress += `<circle id="marker-press-${pt.year}" cx="${getX2(pt.year)}" cy="${getY2(pt.p_req)}" r="3.5" fill="#3b82f6" stroke="var(--card-bg)" stroke-width="1.2" style="transition: r 0.08s ease;" />`;
    });
    
    // Legend Title
    contentPress += `<text x="${pad2.left}" y="${pad2.top - 8}" fill="#3b82f6" font-size="8.5" font-weight="bold" text-anchor="start">REQ. PRESSURE (${currentUnits.pressure})</text>`;
    
    // Invisible Interactive Hover Overlay Slices
    const sliceWidth2 = gw2 / horizon;
    for (let yr = 0; yr <= horizon; yr++) {
        const x = getX2(yr);
        contentPress += `
            <rect x="${x - sliceWidth2/2}" y="${pad2.top}" width="${sliceWidth2}" height="${gh2}" fill="transparent" style="cursor: crosshair;"
                onmouseover="hoverDeclineData(${yr}, 'press', event)"
                onmousemove="hoverDeclineData(${yr}, 'press', event)"
                onmouseout="leaveDeclineData(${yr}, 'press')" />
        `;
    }
    svgPress.innerHTML = contentPress;
}

// Global Hover Interactions for separate charts
function hoverDeclineData(yr, type, event) {
    const pts = window.declineDataPoints;
    if (!pts || pts.length === 0) return;
    const pt = pts.find(p => p.year === yr);
    if (!pt) return;
    
    // 1. Update and position HTML tooltip
    const container = document.getElementById('dec-chart-container');
    const tooltip = document.getElementById('dec-chart-tooltip');
    
    if (tooltip && container) {
        tooltip.style.display = 'block';
        
        const flowLabel = { 'm3/h': 'm³/h', 'm3/d': 'm³/d', 'gpm': 'gpm', 'gpd': 'gpd' }[currentUnits.flow] || 'm³/h';
        let html = `<strong style="color:var(--text-primary); font-size:0.75rem;">Year ${yr}</strong><br/>`;
        if (type === 'npf') {
            html += `<span style="color: var(--success-color);">NPF: ${pt.npf.toFixed(2)} ${flowLabel}</span><br/>`;
            html += `<span style="color: var(--error-color); font-weight: 500;">Drop: ${pt.drop.toFixed(1)}%</span><br/>`;
        } else {
            html += `<span style="color: #3b82f6;">Pressure: ${pt.p_req.toFixed(2)} ${currentUnits.pressure}</span><br/>`;
            html += `<span style="color: var(--success-color);">Act. Flow: ${pt.q_act.toFixed(1)} ${flowLabel}</span><br/>`;
        }
        
        let badgeColor = "var(--success-color)";
        if (pt.status === "REPLACE") badgeColor = "var(--error-color)";
        else if (pt.status === "MONITOR") badgeColor = "var(--warning-color)";
        
        html += `<span style="color:${badgeColor}; font-weight:bold; font-size:0.65rem; border:1px solid ${badgeColor}; padding:0.02rem 0.2rem; border-radius:2px; margin-top:0.2rem; display:inline-block;">${pt.status}</span>`;
        tooltip.innerHTML = html;
        
        const rect = container.getBoundingClientRect();
        const x = event.clientX - rect.left + 15;
        const y = event.clientY - rect.top - 65;
        tooltip.style.left = x + 'px';
        tooltip.style.top = y + 'px';
    }
    
    // 2. Show crosshairs and scale marker dots
    if (type === 'npf') {
        const marker = document.getElementById(`marker-npf-${yr}`);
        if (marker) marker.setAttribute('r', '6');
        
        const cross = document.getElementById('dec-cross-npf');
        if (cross && marker) {
            const xVal = marker.getAttribute('cx');
            cross.setAttribute('x1', xVal);
            cross.setAttribute('x2', xVal);
            cross.style.display = 'block';
        }
    } else {
        const marker = document.getElementById(`marker-press-${yr}`);
        if (marker) marker.setAttribute('r', '6');
        
        const cross = document.getElementById('dec-cross-press');
        if (cross && marker) {
            const xVal = marker.getAttribute('cx');
            cross.setAttribute('x1', xVal);
            cross.setAttribute('x2', xVal);
            cross.style.display = 'block';
        }
    }
}

// Global mouse leave handler
function leaveDeclineData(yr, type) {
    const tooltip = document.getElementById('dec-chart-tooltip');
    if (tooltip) tooltip.style.display = 'none';
    
    if (type === 'npf') {
        const marker = document.getElementById(`marker-npf-${yr}`);
        if (marker) marker.setAttribute('r', '3.5');
        
        const cross = document.getElementById('dec-cross-npf');
        if (cross) cross.style.display = 'none';
    } else {
        const marker = document.getElementById(`marker-press-${yr}`);
        if (marker) marker.setAttribute('r', '3.5');
        
        const cross = document.getElementById('dec-cross-press');
        if (cross) cross.style.display = 'none';
    }
}

// Make hover functions globally available
window.hoverDeclineData = hoverDeclineData;
window.leaveDeclineData = leaveDeclineData;

function generateReportContent() {
    // 1. Set Date
    const today = new Date();
    const dateString = String(today.getDate()).padStart(2, '0') + '/' + String(today.getMonth() + 1).padStart(2, '0') + '/' + today.getFullYear();
    document.getElementById('report-date-str').textContent = 'DATE: ' + dateString;

    // 2. Physical Parameters
    const waterSelect = document.getElementById('water-type');
    const waterType = waterSelect.options[waterSelect.selectedIndex].text || 'Brackish Water';
    document.getElementById('rep-water-type').textContent = waterType;
    
    const flowVal = document.getElementById('flow').value;
    const flowUnit = document.getElementById('flow-unit-label').textContent;
    document.getElementById('rep-flow').textContent = `${flowVal} ${flowUnit}`;
    
    const tempVal = document.getElementById('temp').value;
    const tempUnit = document.getElementById('temp-unit-label').textContent;
    document.getElementById('rep-temp').textContent = `${tempVal} ${tempUnit}`;
    
    document.getElementById('rep-ph').textContent = document.getElementById('ph').value;
    document.getElementById('rep-recovery').textContent = document.getElementById('recovery').value + '%';

    // 3. Feed Chemistry Analysis
    document.getElementById('rep-tds').textContent = document.getElementById('calc-tds').textContent + ' mg/L';
    document.getElementById('rep-ec').textContent = document.getElementById('calc-ec').textContent + ' μS/cm';
    document.getElementById('rep-cbe').textContent = document.getElementById('cbe-display').textContent;
    
    const osmVal = document.getElementById('osmotic-pressure').textContent;
    const pressUnit = document.getElementById('pressure-unit-label').textContent;
    document.getElementById('rep-osm').textContent = `${osmVal} ${pressUnit}`;
    
    document.getElementById('rep-cbe-status').textContent = document.getElementById('cbe-status').textContent;

    // 4. Decline Projections
    const decNpf = document.getElementById('dec-out-npf').textContent;
    const flowLabel = { 'm3/h': 'm³/h', 'm3/d': 'm³/d', 'gpm': 'gpm', 'gpd': 'gpd' }[currentUnits.flow] || 'm³/h';
    document.getElementById('rep-dec-npf').textContent = decNpf !== '—' ? `${decNpf} ${flowLabel}` : '—';
    
    document.getElementById('rep-dec-rate').textContent = document.getElementById('dec-out-rate').textContent;
    document.getElementById('rep-dec-repl').textContent = document.getElementById('dec-out-repl-yr').textContent;
    document.getElementById('rep-dec-status').textContent = document.getElementById('dec-out-status-label').textContent;

    // 5. Year-by-Year Decline Summary Table
    const declineTbody = document.getElementById('decline-results-tbody');
    const reportTbody = document.getElementById('rep-table-tbody');
    if (declineTbody && reportTbody) {
        if (declineTbody.innerHTML.trim().includes('No projection data') || declineTbody.innerHTML.trim().includes('No year-by-year') || declineTbody.innerHTML.trim() === '') {
            reportTbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:1.5rem; color:var(--text-secondary);">No decline projection run. Please configure and run projection on the Performance Decline tab.</td></tr>`;
        } else {
            reportTbody.innerHTML = declineTbody.innerHTML;
        }
    }

    // 6. Pre-treatment remarks
    const preText = document.getElementById('pretreatment-text');
    const repRemarks = document.getElementById('rep-pretreatment-remarks');
    if (preText && repRemarks) {
        const preHtml = preText.innerHTML;
        if (preHtml.trim() !== "") {
            repRemarks.innerHTML = preHtml;
        } else {
            repRemarks.innerHTML = "<ul><li>All physical parameters are within standard operating limits.</li><li>Standard pre-treatment (5 μm cartridge filter) is sufficient.</li></ul>";
        }
    }
}

// Chart.js Initialization
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    const ctx = document.getElementById('siChart');
    if (ctx) {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const tickColor = isDark ? '#94a3b8' : '#475569';
        const labelColor = isDark ? '#f8fafc' : '#1e293b';

        window.siChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Calcite (CaCO₃)', 'Gypsum', 'Silica', 'Fe(OH)₃', 'Al(OH)₃', 'Pyrolusite', 'Hydroxyapatite', 'Anhydrite', 'Barite', 'Celestite', 'Fluorite'],
                datasets: [{
                    label: 'Saturation Index (log10)',
                    data: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    backgroundColor: 'rgba(79, 70, 229, 0.8)',
                    borderColor: 'rgb(79, 70, 229)',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: labelColor, font: { family: 'Inter', size: 13 } }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleColor: '#38bdf8',
                        bodyColor: '#f8fafc',
                        borderColor: 'rgba(56, 189, 248, 0.4)',
                        borderWidth: 1,
                        padding: 14,
                        cornerRadius: 8,
                        displayColors: false,
                        titleFont: { family: 'Inter', size: 14, weight: '600' },
                        bodyFont: { family: 'Inter', size: 13 }
                    }
                },
                scales: {
                    y: {
                        grid: { 
                            color: (context) => {
                                const activeDark = document.documentElement.getAttribute('data-theme') === 'dark';
                                if (context.tick.value === 0) {
                                    return activeDark ? 'rgba(255, 255, 255, 0.5)' : 'rgba(0, 0, 0, 0.3)';
                                }
                                return activeDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';
                            },
                            lineWidth: (context) => context.tick.value === 0 ? 2 : 1,
                            borderDash: (context) => context.tick.value === 0 ? [] : [5, 5]
                        },
                        ticks: { color: tickColor, font: { family: 'Inter' } },
                        title: { display: true, text: 'Saturation Index (log10)', color: tickColor, font: { family: 'Inter', size: 13 } }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: tickColor, font: { family: 'Inter', size: 12 } }
                    }
                }
            }
        });
    }
});

window.clearIonicData = function() {
    document.querySelectorAll('.ion-input').forEach(input => {
        input.value = 0;
        input.dispatchEvent(new Event('input'));
    });
    if (typeof calculateChemistry === 'function') {
        calculateChemistry(false);
    }
};

window.runAutoBalance = function() {
    const getVal = (id) => {
        const el = document.getElementById(id);
        if (!el) return 0;
        return parseFloat(el.value || el.textContent) || 0;
    };
    
    const ph = getVal('ph') || 7.0;
    const calcium = getVal('ca');
    const magnesium = getVal('mg');
    const sodium = getVal('na');
    const potassium = getVal('k');
    const ammonium = getVal('nh4');
    const barium = getVal('ba');
    const strontium = getVal('sr');
    const chloride = getVal('cl');
    const sulfate = getVal('so4');
    const bicarbonate = getVal('hco3');
    const carbonate = getVal('co3');
    const nitrate = getVal('no3');
    const fluoride = getVal('f');
    const phosphate = getVal('po4');

    const mw = {
        ca: 40.08, z_ca: 2,
        mg: 24.31, z_mg: 2,
        na: 22.99, z_na: 1,
        k: 39.10, z_k: 1,
        nh4: 18.04, z_nh4: 1,
        ba: 137.33, z_ba: 2,
        sr: 87.62, z_sr: 2,
        cl: 35.45, z_cl: 1,
        so4: 96.06, z_so4: 2,
        hco3: 61.02, z_hco3: 1,
        co3: 60.01, z_co3: 2,
        no3: 62.00, z_no3: 1,
        f: 19.00, z_f: 1,
        po4: 94.97, z_po4: 3
    };

    const hco3_meq = (bicarbonate / mw.hco3) * mw.z_hco3;
    const co3_meq = (carbonate / mw.co3) * mw.z_co3;

    const cat_meq = 
        (calcium / mw.ca) * mw.z_ca +
        (magnesium / mw.mg) * mw.z_mg +
        (sodium / mw.na) * mw.z_na +
        (potassium / mw.k) * mw.z_k +
        (ammonium / mw.nh4) * mw.z_nh4 +
        (barium / mw.ba) * mw.z_ba +
        (strontium / mw.sr) * mw.z_sr;

    const an_meq = 
        (chloride / mw.cl) * mw.z_cl +
        (sulfate / mw.so4) * mw.z_so4 +
        hco3_meq + co3_meq +
        (nitrate / mw.no3) * mw.z_no3 +
        (fluoride / mw.f) * mw.z_f +
        (phosphate / mw.po4) * mw.z_po4;

    const cbe_meq = cat_meq - an_meq;
    const denom = Math.max(cat_meq + an_meq, 0.1);
    const cbe_pct = (cbe_meq / denom) * 100;

    let na_final = sodium;
    let cl_final = chloride;

    if (Math.abs(cbe_pct) > 2.0) {
        if (cbe_meq > 0) {
            const injected = cbe_meq * (mw.cl / mw.z_cl);
            cl_final += injected;
        } else {
            const injected = Math.abs(cbe_meq) * (mw.na / mw.z_na);
            na_final += injected;
        }
    }

    const naInput = document.getElementById('na');
    const clInput = document.getElementById('cl');
    if (naInput) {
        naInput.value = na_final.toFixed(2);
        naInput.dispatchEvent(new Event('input'));
    }
    if (clInput) {
        clInput.value = cl_final.toFixed(2);
        clInput.dispatchEvent(new Event('input'));
    }
};


// Calculation Module Logic
document.addEventListener('DOMContentLoaded', () => {
    
    // Recycle UI Logic
    const recycleEnable = document.getElementById('calc-recycle-enable');
    const recycleOptions = document.getElementById('calc-recycle-options');
    const recycleRatio = document.getElementById('calc-recycle-ratio');
    const recycleValDisplay = document.getElementById('calc-recycle-val');
    
    if (recycleEnable && recycleOptions) {
        recycleEnable.addEventListener('change', (e) => {
            recycleOptions.style.display = e.target.checked ? 'block' : 'none';
        });
    }
    
    if (recycleRatio && recycleValDisplay) {
        recycleRatio.addEventListener('input', (e) => {
            recycleValDisplay.innerText = e.target.value;
        });
    }

    // Toggle UF module dropdown and Pass 2 container based on train selection
    const trainSelect = document.getElementById('calc-tech-train');
    if (trainSelect) {
        trainSelect.addEventListener('change', (e) => {
            const train = e.target.value;

            // ── Show / hide UF module input ─────────────────────────────────
            const ufGroup = document.getElementById('calc-uf-module-group');
            if (ufGroup) ufGroup.style.display = train.includes('UF') ? 'block' : 'none';

            // ── Show / hide UF economic parameters row ───────────────────────
            const ufEcoRow = document.getElementById('eco-uf-params-row');
            if (ufEcoRow) {
                ufEcoRow.style.display = train.includes('UF') ? 'grid' : 'none';
                // Set default UF module cost from the selected UF module
                if (train.includes('UF')) {
                    const ufModSel = document.getElementById('calc-uf-module');
                    const ufModCostEl = document.getElementById('eco-uf-mod-cost');
                    if (ufModSel && ufModCostEl) {
                        const ufModCosts = { 'IntegraTec-SFD-2880': 120000, 'SFP-2860': 85000 };
                        ufModCostEl.value = ufModCosts[ufModSel.value] || 120000;
                    }
                }
            }

            // ── Show / hide Pass 2 container ────────────────────────────────
            const pass2Container = document.getElementById('calc-pass2-container');
            if (pass2Container) pass2Container.style.display = train.includes('2P-RO') ? 'block' : 'none';

            // ── Reset inputs to sensible defaults for this train ────────────
            const defaults = {
                'RO':     { recovery: 75, stages: 2, vessels: '4, 2', elements: 6 },
                'UF-RO':  { recovery: 75, stages: 2, vessels: '4, 2', elements: 6 },
                'NF':     { recovery: 80, stages: 1, vessels: '4',    elements: 6 },
                '2P-RO':  { recovery: 75, stages: 2, vessels: '4, 2', elements: 6 },
            };
            const d = defaults[train] || defaults['RO'];

            const recoveryEl = document.getElementById('calc-target-recovery');
            const stagesEl   = document.getElementById('calc-stages');
            const vesselsEl  = document.getElementById('calc-vessels-array');
            const elemsEl    = document.getElementById('calc-elements-pv');

            if (recoveryEl) recoveryEl.value = d.recovery;
            if (stagesEl)   stagesEl.value   = d.stages;
            if (vesselsEl)  vesselsEl.value   = d.vessels;
            if (elemsEl)    elemsEl.value     = d.elements;

            // For 2P-RO reset Pass 2 defaults too
            if (train.includes('2P-RO')) {
                const p2Stages  = document.getElementById('calc-p2-stages');
                const p2Vessels = document.getElementById('calc-p2-vessels-array');
                const p2Elems   = document.getElementById('calc-p2-elements-pv');
                const p2Recovery= document.getElementById('calc-p2-recovery');
                if (p2Stages)   p2Stages.value   = 1;
                if (p2Vessels)  p2Vessels.value   = '2';
                if (p2Elems)    p2Elems.value     = 6;
                if (p2Recovery) p2Recovery.value  = 85;
            }

            // ── Clear all results so user starts fresh ──────────────────────
            const resultsContainer = document.getElementById('calc-results-container');
            if (resultsContainer) {
                resultsContainer.style.display = 'none';
            }

            // Clear year-wise physics table and cards safely
            const physTbody = document.getElementById('phys-annual-tbody');
            if (physTbody) physTbody.innerHTML = '';
            const physBanner = document.getElementById('phys-year-banner');
            if (physBanner) physBanner.style.display = 'none';
            ['phys-card-press','phys-card-flow','phys-card-npf','phys-card-fri',
             'phys-card-brel','phys-card-rec','phys-card-tds','phys-card-sec','phys-card-cips']
            .forEach(id => { const el = document.getElementById(id); if (el) el.innerText = '-'; });

            // Reset Calculate button state if it was in loading state
            const calcBtn = document.getElementById('calculate-btn');
            if (calcBtn) {
                calcBtn.disabled = false;
                calcBtn.textContent = 'Calculate';
            }
        });
        // Trigger initial toggle (without clearing results on first load)
        const ufGroup = document.getElementById('calc-uf-module-group');
        if (ufGroup) ufGroup.style.display = trainSelect.value.includes('UF') ? 'block' : 'none';
        const pass2Container = document.getElementById('calc-pass2-container');
        if (pass2Container) pass2Container.style.display = trainSelect.value.includes('2P-RO') ? 'block' : 'none';
    }

    // Sync vessels array when stages input changes to prevent errors
    const stagesInput = document.getElementById('calc-stages');
    const vesselsInput = document.getElementById('calc-vessels-array');
    if (stagesInput && vesselsInput) {
        stagesInput.addEventListener('change', () => {
            const stages = parseInt(stagesInput.value) || 1;
            const currentVessels = vesselsInput.value.split(',').map(s => s.trim()).filter(s => s);
            let newVessels = [];
            const defaultVessels = [4, 2, 1, 1];
            for (let i = 0; i < stages; i++) {
                if (i < currentVessels.length) {
                    newVessels.push(currentVessels[i]);
                } else {
                    newVessels.push(defaultVessels[i] || 1);
                }
            }
            vesselsInput.value = newVessels.join(', ');
        });
        vesselsInput.addEventListener('input', () => {
            const currentVessels = vesselsInput.value.split(/[\s,:\-;]+/).map(s => s.trim()).filter(s => s && !isNaN(parseInt(s)));
            if (currentVessels.length > 0 && currentVessels.length <= 4) {
                const stagesInput = document.getElementById('calc-stages');
                if (stagesInput && parseInt(stagesInput.value) !== currentVessels.length) {
                    stagesInput.value = currentVessels.length;
                    stagesInput.dispatchEvent(new Event('change'));
                }
            }
        });
    }
    // Sync Pass 2 vessels array when stages input changes to prevent errors
    const p2StagesInput = document.getElementById('calc-p2-stages');
    const p2VesselsInput = document.getElementById('calc-p2-vessels-array');
    if (p2StagesInput && p2VesselsInput) {
        p2StagesInput.addEventListener('change', () => {
            const stages = parseInt(p2StagesInput.value) || 1;
            const currentVessels = p2VesselsInput.value.split(',').map(s => s.trim()).filter(s => s);
            let newVessels = [];
            const defaultVessels = [2, 1, 1, 1];
            for (let i = 0; i < stages; i++) {
                if (i < currentVessels.length) {
                    newVessels.push(currentVessels[i]);
                } else {
                    newVessels.push(defaultVessels[i] || 1);
                }
            }
            p2VesselsInput.value = newVessels.join(', ');
        });
        p2VesselsInput.addEventListener('input', () => {
            const currentVessels = p2VesselsInput.value.split(/[\s,:\-;]+/).map(s => s.trim()).filter(s => s && !isNaN(parseInt(s)));
            if (currentVessels.length > 0 && currentVessels.length <= 4) {
                const p2StagesInput = document.getElementById('calc-p2-stages');
                if (p2StagesInput && parseInt(p2StagesInput.value) !== currentVessels.length) {
                    p2StagesInput.value = currentVessels.length;
                    p2StagesInput.dispatchEvent(new Event('change'));
                }
            }
        });
    }

    // Auto-select best membrane based on target recovery
    const targetRecoveryInput = document.getElementById('calc-target-recovery');
    if (targetRecoveryInput) {
        let autoSelectTimer = null;
        const runAutoSelect = async () => {
            console.log('[AutoSelect] Triggered, recovery =', targetRecoveryInput.value);
            try {
                const safeVal = (id) => {
                    const el = document.getElementById(id);
                    if (!el) return 0;
                    return parseFloat(el.value || el.textContent) || 0;
                };

                const feedData = {
                    calcium: safeVal('ca'),
                    magnesium: safeVal('mg'),
                    sodium: safeVal('na'),
                    potassium: safeVal('k'),
                    chloride: safeVal('cl'),
                    sulfate: safeVal('so4'),
                    bicarbonate: safeVal('hco3'),
                    strontium: safeVal('sr'),
                    fluoride: safeVal('fluoride') || safeVal('f'),
                    silica: safeVal('sio2'),
                    boron: safeVal('boron'),
                    nitrate: safeVal('no3'),
                    phosphate: safeVal('po4'),
                    ammonium: safeVal('nh4'),
                    iron: safeVal('fe'),
                    manganese: safeVal('mn'),
                    temperature: safeVal('temp') || 25,
                    ph: safeVal('ph') || 7.5
                };

                const vesselsStr = (document.getElementById('calc-vessels-array') || {}).value || "4, 2";
                const vessels = vesselsStr.split(',').map(s => parseInt(s.trim()) || 1);

                const payload = {
                    technology_train: document.getElementById('calc-tech-train').value,
                    feed_water: feedData,
                    target_flow_m3h: parseFloat(document.getElementById('flow').value) || 100,
                    target_recovery_pct: parseFloat(targetRecoveryInput.value) || 75,
                    ro_membrane: "BW30-400",
                    uf_module: document.getElementById('calc-tech-train').value.includes('UF') ? document.getElementById('calc-uf-module').value : null,
                    stages: parseInt(document.getElementById('calc-stages').value) || 2,
                    vessels_per_stage: vessels,
                    elements_per_vessel: parseInt(document.getElementById('calc-elements-pv').value) || 6,
                    source_type: document.getElementById('water-type') && document.getElementById('water-type').selectedIndex !== -1 ? (document.getElementById('water-type').options[document.getElementById('water-type').selectedIndex].getAttribute('data-source-type') || 'LOW_TDS') : 'LOW_TDS'
                };

                console.log('[AutoSelect] Sending payload:', JSON.stringify(payload));
                const res = await fetch(API_BASE + '/api/auto-select-membrane', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                console.log('[AutoSelect] Response status:', res.status);
                if (res.ok) {
                    const data = await res.json();
                    console.log('[AutoSelect] Result:', data);
                    if (data.best_membrane) {
                        const memSelect = document.getElementById('calc-ro-membrane');
                        if (memSelect) {
                            memSelect.value = data.best_membrane;
                            memSelect.dispatchEvent(new Event('change'));
                        }
                        // Show a temporary toast notification
                        const toast = document.createElement('div');
                        toast.style.cssText = 'position:fixed;top:20px;right:20px;background:linear-gradient(135deg,#10b981,#059669);color:#fff;padding:14px 24px;border-radius:12px;z-index:99999;font-family:Inter,sans-serif;font-size:14px;box-shadow:0 8px 32px rgba(0,0,0,0.3);max-width:400px;transition:opacity 0.5s;';
                        toast.textContent = `✓ Auto-selected ${data.best_membrane} — max recovery ${(data.max_recovery * 100).toFixed(1)}%`;
                        document.body.appendChild(toast);
                        setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 500); }, 3500);
                    }
                } else {
                    console.error('[AutoSelect] Server error:', await res.text());
                }
            } catch (err) {
                console.error("[AutoSelect] Failed:", err);
            }
        };

        // Disabled auto-selection of membranes based on target recovery by request.
        /*
        targetRecoveryInput.addEventListener('input', () => {
            clearTimeout(autoSelectTimer);
            autoSelectTimer = setTimeout(runAutoSelect, 800);
        });
        targetRecoveryInput.addEventListener('change', () => {
            clearTimeout(autoSelectTimer);
            runAutoSelect();
        });
        */
    }

    // Auto-design vessel array based on feed flow and target recovery
    const autoDesignVesselArray = () => {
        const flowInput = document.getElementById('flow');
        const recoveryInput = document.getElementById('calc-target-recovery');
        const stagesInput = document.getElementById('calc-stages');
        const elementsPvInput = document.getElementById('calc-elements-pv');
        const waterTypeInput = document.getElementById('water-type');
        const vesselsArrayInput = document.getElementById('calc-vessels-array');
        
        if (!flowInput || !recoveryInput || !vesselsArrayInput) return;
        
        const feedFlow = parseFloat(flowInput.value) || 50;
        const targetRec = (parseFloat(recoveryInput.value) || 75) / 100;
        const stages = parseInt(stagesInput ? stagesInput.value : 2) || 2;
        const elementsPV = parseInt(elementsPvInput ? elementsPvInput.value : 6) || 6;
        
        let targetFlux = 20; // default LMH
        if (waterTypeInput && waterTypeInput.options[waterTypeInput.selectedIndex]) {
            const sourceType = waterTypeInput.options[waterTypeInput.selectedIndex].dataset.sourceType || '';
            if (sourceType.includes('SEAWATER')) targetFlux = 14;
            else if (sourceType.includes('WELL') || sourceType.includes('GW')) targetFlux = 25;
            else if (sourceType.includes('WASTEWATER')) targetFlux = 15;
            else if (sourceType.includes('PERMEATE')) targetFlux = 30;
        }
        
        const permFlow = feedFlow * targetRec;
        const totalAreaNeeded = (permFlow * 1000) / targetFlux;
        
        let avgElementArea = 37.16; // ~400 sq ft standard
        const memSelect = document.getElementById('calc-ro-membrane');
        if (memSelect && window.roMembranes) {
            const selectedMem = memSelect.value;
            if (window.roMembranes[selectedMem] && window.roMembranes[selectedMem].active_area_m2) {
                avgElementArea = window.roMembranes[selectedMem].active_area_m2;
            }
        }
        
        const totalElements = Math.ceil(totalAreaNeeded / avgElementArea);
        const totalVessels = Math.max(stages, Math.ceil(totalElements / elementsPV));
        
        let vesselsArray = [];
        if (stages === 1) {
            vesselsArray = [totalVessels];
        } else if (stages === 2) {
            const stage1 = Math.ceil(totalVessels * 2 / 3);
            const stage2 = Math.max(1, totalVessels - stage1);
            vesselsArray = [stage1, stage2];
        } else if (stages === 3) {
            const stage1 = Math.ceil(totalVessels * 4 / 7);
            const stage2 = Math.ceil(totalVessels * 2 / 7);
            const stage3 = Math.max(1, totalVessels - stage1 - stage2);
            vesselsArray = [stage1, stage2, stage3];
        } else {
            let rem = totalVessels;
            for (let i = 0; i < stages; i++) {
                let v = Math.ceil(rem / (stages - i));
                vesselsArray.push(Math.max(1, v));
                rem -= v;
            }
        }
        vesselsArrayInput.value = vesselsArray.join(', ');
        // Trigger input event to update PFD dynamically
        vesselsArrayInput.dispatchEvent(new Event('input'));
    };

    // Attach listeners for auto-design
    const designInputs = ['flow', 'calc-target-recovery', 'calc-stages', 'calc-elements-pv', 'water-type'];
    designInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            // el.addEventListener('input', autoDesignVesselArray);
            // el.addEventListener('change', autoDesignVesselArray);
        }
    });

    const calcBtn = document.getElementById('calc-run-btn');

    // Auto-calculate is intentionally removed so computations only run on explicit button click
    const triggerAutoCalc = () => {}; 
    const allCalcInputs = document.querySelectorAll('#feed-dashboard-view input, #feed-dashboard-view select, #calculation-panel-view input, #calculation-panel-view select');
    // Removed auto-calculation event listeners for allCalcInputs

    if (calcBtn) {
        calcBtn.addEventListener('click', async () => {
            const loading = document.getElementById('calc-loading-indicator');
            const results = document.getElementById('calc-results-container');
            const runBtn = document.getElementById('calc-run-btn');
            
            if (loading) loading.style.display = 'none'; // Ensure old loader is hidden
            if (window.showLoader) window.showLoader();
            
            if (results.style.display !== 'flex') {
                results.style.display = 'none';
            } else {
                results.style.opacity = '0.5';
            }
            runBtn.disabled = true;

            // Yield to browser to paint the loader before heavy synchronous calculation
            await new Promise(r => setTimeout(r, 50));

            // Trigger local module calculations
            try {
                if (typeof calculateChemistry === 'function') calculateChemistry(true);
                if (typeof calculatePreTreatment === 'function') calculatePreTreatment(true);
                if (typeof runDeclineProjection === 'function') runDeclineProjection();
            } catch (err) {
                console.error("Local calculation error:", err);
            }

            try {
                // Gather feed data safely
                const safeVal = (id, fallback = 0) => {
                    const el = document.getElementById(id);
                    if (!el) return fallback;
                    return parseFloat(el.value || el.textContent) || fallback;
                };

                const safeStr = (id, fallback = '') => {
                    const el = document.getElementById(id);
                    if (!el) return fallback;
                    return el.value || el.textContent || fallback;
                };

                const feedData = {
                    calcium: safeVal('ca'),
                    magnesium: safeVal('mg'),
                    sodium: safeVal('na'),
                    potassium: safeVal('k'),
                    barium: safeVal('ba'),
                    strontium: safeVal('sr'),
                    chloride: safeVal('cl'),
                    sulfate: safeVal('so4'),
                    bicarbonate: safeVal('hco3'),
                    nitrate: safeVal('no3'),
                    fluoride: safeVal('f'),
                    silica: safeVal('sio2'),
                    boron: safeVal('b'),
                    phosphate: safeVal('po4'),
                    aluminium: safeVal('al'),
                    iron: safeVal('fe'),
                    manganese: safeVal('mn'),
                    temperature: safeVal('temp') || 25,
                    ph: safeVal('ph') || 7.0,
                    tds: safeVal('calc-tds'), // calc-tds is a span with textContent
                    tss: safeVal('tss'),
                    turbidity: safeVal('turbidity')
                };


                const vesselsStr = safeStr('calc-vessels-array', '4, 2');
                const vessels = vesselsStr.split(',').map(s => parseInt(s.trim()) || 1);

                // Pass 1 config (corresponds to first pass inputs)
                const pass1 = {
                    membrane: safeStr('calc-ro-membrane', 'BW30-400'),
                    stages: parseInt(safeVal('calc-stages', 2)),
                    vessels_per_stage: vessels,
                    elements_per_vessel: parseInt(safeVal('calc-elements-pv', 6)),
                    target_recovery_pct: parseFloat(safeVal('calc-target-recovery', 75))
                };

                // Pass 2 config
                const p2VesselsStr = safeStr('calc-p2-vessels-array', '2');
                const p2Vessels = p2VesselsStr.split(',').map(s => parseInt(s.trim()) || 1);
                const pass2 = {
                    membrane: safeStr('calc-p2-membrane', 'BW30-400'),
                    stages: parseInt(safeVal('calc-p2-stages', 1)),
                    vessels_per_stage: p2Vessels,
                    elements_per_vessel: parseInt(safeVal('calc-p2-elements-pv', 6)),
                    target_recovery_pct: parseFloat(safeVal('calc-p2-recovery', 85))
                };

                // Conditioning config
                const conditioning = {
                    enabled: safeStr('calc-cond-enabled', 'false') === 'true',
                    target_ph: parseFloat(safeVal('calc-cond-ph', 9.8)),
                    chemical: safeStr('calc-cond-chem', 'NaOH'),
                    co2_degassing: safeStr('calc-cond-degas', 'false') === 'true'
                };

                // Recycle config
                const recycleObj = {
                    enabled: document.getElementById('calc-recycle-enable') ? document.getElementById('calc-recycle-enable').checked : false,
                    recycle_ratio: parseFloat(safeVal('calc-recycle-ratio', 0)) / 100.0
                };

                const payload = {
                    technology_train: safeStr('calc-tech-train', 'RO'),
                    project_details: {
                        name: safeStr('proj-name', 'PACE Report'),
                        author: safeStr('proj-engineer', ''),
                        company: safeStr('proj-company', ''),
                        date: safeStr('proj-date', '')
                    },
                    feed_water: feedData,
                    target_flow_m3h: safeVal('flow', 100),
                    target_recovery_pct: safeVal('calc-target-recovery', 75),
                    ro_membrane: safeStr('calc-ro-membrane', 'BW30-400'),
                    uf_module: safeStr('calc-tech-train', 'RO').includes('UF') ? safeStr('calc-uf-module', null) : null,
                    stages: parseInt(safeVal('calc-stages', 2)),
                    vessels_per_stage: vessels,
                    elements_per_vessel: parseInt(safeVal('calc-elements-pv', 6)),
                    recycle_enabled: document.getElementById('calc-recycle-enable') ? document.getElementById('calc-recycle-enable').checked : false,
                    recycle_ratio: safeVal('calc-recycle-ratio', 0) / 100.0,
                    
                    // Sub-objects for Two-Pass RO
                    pass1: pass1,
                    pass2: pass2,
                    conditioning: conditioning,
                    recycle: recycleObj,
                    
                    economic_params: {
                        electricity_tariff: safeVal('eco-tariff', 7.50),
                        membrane_cost: safeVal('eco-mem-cost', 26880),
                        vessel_cost: safeVal('eco-ves-cost', 48000),
                        pump_cost_kw: safeVal('eco-pump-cost', 96000),
                        ic_factor: safeVal('eco-ic-factor', 15) / 100,
                        contingency_factor: safeVal('eco-cont-factor', 10) / 100,
                        membrane_lifetime: safeVal('eco-mem-life', 5),
                        plant_availability: safeVal('eco-avail', 90) / 100,
                        discount_rate: 0.10,
                        project_life: 20,
                        uf_module_cost: safeVal('eco-uf-mod-cost', 120000),
                        uf_membrane_lifetime: safeVal('eco-uf-mem-life', 7)
                    }
                };

                const isPhysics = document.getElementById('calc-physics-enable') && document.getElementById('calc-physics-enable').checked;
                if (isPhysics) {
                    payload.projection_year = parseInt(safeVal('phys-selected-year', 0));
                    payload.n_years = 5;
                    payload.feed_quality = {
                        sdi15: safeVal('aging-sdi', 3.0),
                        toc_mg_l: safeVal('aging-toc', 2.0),
                        cl2_residual_mg_l: parseFloat(document.getElementById('cl2').value) || 0.0
                    };
                    payload.cip_config = {
                        interval_months: parseInt(safeVal('phys-cip-interval', 0)),
                        duration_h: 4.0
                    };
                    const agingCheckbox = document.getElementById('aging-antiscalant');
                    const physDropdown = document.getElementById('phys-antiscalant');
                    let asDosed = true;
                    if (agingCheckbox && agingCheckbox.offsetParent !== null) {
                        asDosed = agingCheckbox.checked;
                    } else if (physDropdown) {
                        asDosed = physDropdown.value === 'true';
                    } else if (agingCheckbox) {
                        asDosed = agingCheckbox.checked;
                    }
                    payload.antiscalant_dosed = asDosed;
                }

                const url = isPhysics ? API_BASE + '/api/calculate-system-physics' : API_BASE + '/api/calculate-system';

                const res = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                if (!res.ok) throw new Error(await res.text());
                const data = await res.json();

                // ── 2P-RO compatibility shim ────────────────────────────────
                // The 2P-RO backend returns pass1_results/pass2_results, but the
                // render block expects ro_results. Alias pass1_results so that
                // all existing render code works unchanged for the overview cards,
                // stage tables, booster pumps, ion table and warnings.
                if (!data.ro_results && data.pass1_results) {
                    data.ro_results = data.pass1_results;
                    // Build a combined summary for the top-level KPI cards
                    const sys = data.system_summary || {};
                    const p1s = data.pass1_results.summary;
                    const p2s = data.pass2_results ? data.pass2_results.summary : {};
                    data.ro_results.summary = {
                        ...p1s,
                        // Override with combined Two-Pass values
                        total_recovery:     sys.overall_recovery      ?? p1s.total_recovery,
                        perm_flow:          sys.final_permeate_flow_m3h ?? p1s.perm_flow,
                        perm_tds:           sys.final_permeate_tds    ?? p1s.perm_tds,
                        sec_kwh_m3:         sys.sec_kwh_m3            ?? p1s.sec_kwh_m3,
                        feed_pressure_bar:  p1s.feed_pressure_bar,
                    };
                }

                // Store last calculation results globally
                window.lastCalcResult = data;

                const physSubtabBtn = document.getElementById('calc-subtab-physics');
                if (physSubtabBtn) {
                    // Always keep the tab visible so the user can revert back to it
                    physSubtabBtn.style.display = 'inline-flex';
                }

                if (isPhysics && data.physics_results) {
                    window.renderPhysicsResults(data);
                }
                
                // Render UF results
                const ufResultsCard = results.querySelector('#calc-uf-results-card');
                if (data.uf_results) {
                    if (ufResultsCard) {
                        ufResultsCard.style.display = 'block';
                        const ufModules = results.querySelector('#calc-uf-modules');
                        const ufFlux    = results.querySelector('#calc-uf-flux');
                        const ufRec     = results.querySelector('#calc-uf-rec');
                        const ufTmp     = results.querySelector('#calc-uf-tmp');
                        if (ufModules) ufModules.innerText = data.uf_results.overview.total_modules;
                        
                        const fluxConv = conversions.flux ? conversions.flux.fromBase(data.uf_results.operating_conditions.filtration_flux_lmh, currentUnits.flux || 'LMH') : data.uf_results.operating_conditions.filtration_flux_lmh;
                        const tmpConv = conversions.pressure.fromBase(data.uf_results.overview.tmp_design_bar, currentUnits.pressure);
                        
                        if (ufFlux)    ufFlux.innerText    = fluxConv.toFixed(1);
                        if (ufRec)     ufRec.innerText     = data.uf_results.overview.recovery_pct.toFixed(1);
                        if (ufTmp)     ufTmp.innerText     = tmpConv.toFixed(2);
                        
                        const setT = (sel, val) => { const el = results.querySelector(sel); if (el) el.innerText = val; };
                        setT('#calc-uf-flux-unit', currentUnits.flux || 'LMH');
                        setT('#calc-uf-tmp-unit', currentUnits.pressure);
                    }
                } else {
                    if (ufResultsCard) ufResultsCard.style.display = 'none';
                }

                // Format INR utility function
                function formatINR(number) {
                    if (number >= 10000000) {
                        return '₹' + (number / 10000000).toFixed(2) + ' Cr';
                    } else if (number >= 100000) {
                        return '₹' + (number / 100000).toFixed(2) + ' L';
                    } else {
                        return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(number);
                    }
                }

                // Render Economics
                if (data.economics) {
                    const eco = data.economics;
                    
                    // Update input boxes to reflect dynamic backend logic if present
                    if (eco.unit_membrane_cost_inr) {
                        const ecoMemInput = document.getElementById('eco-mem-cost');
                        if (ecoMemInput) {
                            ecoMemInput.value = eco.unit_membrane_cost_inr;
                        }
                    }

                    // Safe setter for economics fields
                    const setEco = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };

                    // CAPEX
                    setEco('eco-capex-mem',   formatINR(eco.capex.membranes_inr));
                    setEco('eco-capex-ves',   formatINR(eco.capex.vessels_inr));
                    setEco('eco-capex-hp',    formatINR(eco.capex.hp_pump_inr));
                    setEco('eco-capex-bp',    formatINR(eco.capex.booster_pump_inr));
                    setEco('eco-capex-sub',   formatINR(eco.capex.equip_subtotal_inr));
                    setEco('eco-capex-ic',    formatINR(eco.capex.ic_inr));
                    setEco('eco-capex-cont',  formatINR(eco.capex.contingency_inr));
                    setEco('eco-capex-total', formatINR(eco.capex.total_capex_inr));

                    // Show/hide UF CAPEX rows
                    const ufModCost = eco.capex.uf_modules_inr || 0;
                    const ufPumpCost = eco.capex.uf_pumps_inr || 0;
                    const ufModRow  = document.getElementById('eco-capex-uf-mod-row');
                    const ufPumpRow = document.getElementById('eco-capex-uf-pump-row');
                    if (ufModRow)  ufModRow.style.display  = ufModCost  > 0 ? 'table-row' : 'none';
                    if (ufPumpRow) ufPumpRow.style.display = ufPumpCost > 0 ? 'table-row' : 'none';
                    if (ufModCost  > 0) setEco('eco-capex-uf-mod',  formatINR(ufModCost)  + (eco.capex.uf_modules_count ? ` (${eco.capex.uf_modules_count} modules)` : ''));
                    if (ufPumpCost > 0) setEco('eco-capex-uf-pump', formatINR(ufPumpCost));

                    // OPEX
                    setEco('eco-opex-energy', formatINR(eco.opex.energy_cost_pa_inr));
                    // Show RO-only membrane replacement in its row
                    setEco('eco-opex-mem',    formatINR(eco.opex.ro_mem_repl_pa_inr !== undefined
                                                        ? eco.opex.ro_mem_repl_pa_inr
                                                        : eco.opex.membrane_repl_pa_inr));
                    setEco('eco-opex-total',  formatINR(eco.opex.total_opex_pa_inr));

                    // Show/hide UF Module Replacement row
                    const ufMemRepl = eco.opex.uf_mem_repl_pa_inr || 0;
                    const ufMemReplRow = document.getElementById('eco-opex-uf-mem-row');
                    if (ufMemReplRow) ufMemReplRow.style.display = ufMemRepl > 0 ? 'table-row' : 'none';
                    if (ufMemRepl > 0) setEco('eco-opex-uf-mem', formatINR(ufMemRepl));

                    // Show/hide UF OPEX CEB chemicals row
                    const ufChemCost = eco.opex.uf_ceb_chemicals_pa_inr || 0;
                    const ufChemRow  = document.getElementById('eco-opex-uf-chem-row');
                    if (ufChemRow) ufChemRow.style.display = ufChemCost > 0 ? 'table-row' : 'none';
                    if (ufChemCost > 0) setEco('eco-opex-uf-chem', formatINR(ufChemCost));

                    // Unit Cost
                    setEco('eco-metrics-kl',       new Intl.NumberFormat('en-IN').format(eco.metrics.annual_production_kl));
                    setEco('eco-metrics-tac',       formatINR(eco.metrics.total_annual_cost_inr));
                    setEco('eco-metrics-cost-kl',   '₹' + eco.metrics.cost_per_kl_inr.toFixed(2));
                }
                
                // Render RO results
                if (data.ro_results) {
                    const roSum = data.ro_results.summary;
                    const setR = (sel, val) => { const el = results.querySelector(sel); if (el) el.innerText = val; };
                    
                    const flowLabel = { 'm3/h': 'm³/h', 'm3/d': 'm³/d', 'gpm': 'gpm', 'gpd': 'gpd' }[currentUnits.flow] || 'm³/h';
                    const pressLabel = currentUnits.pressure;
                    
                    const sysFlowConv = conversions.flow.fromBase(roSum.perm_flow, currentUnits.flow);
                    const sysPressConv = conversions.pressure.fromBase(roSum.feed_pressure_bar, currentUnits.pressure);
                    
                    setR('#calc-sys-rec',       (roSum.total_recovery * 100).toFixed(1));
                    setR('#calc-sys-perm-flow', sysFlowConv.toFixed(1));
                    setR('#calc-sys-press',     sysPressConv.toFixed(1));
                    setR('#calc-sys-tds',       roSum.perm_tds.toFixed(1));
                    setR('#calc-sys-sec',       roSum.sec_kwh_m3.toFixed(2));
                    
                    setR('#calc-sys-perm-flow-unit', flowLabel);
                    setR('#calc-sys-press-unit', pressLabel);
                    
                    // Render Recycle Summary
                    const recycleCard = results.querySelector('#calc-recycle-summary-card');
                    if (data.recycle && data.recycle.enabled) {
                        if (recycleCard) recycleCard.style.display = 'block';
                        
                        const elEffRec = results.querySelector('#calc-rec-eff-rec');
                        if (elEffRec) elEffRec.innerText = data.recycle.effective_system_recovery_pct.toFixed(1);

                        const elRecPress = results.querySelector('#calc-rec-press');
                        const recPressConv = conversions.pressure.fromBase(data.recycle.feed_pressure_bar, currentUnits.pressure);
                        if (elRecPress) elRecPress.innerText = recPressConv.toFixed(1);
                        setR('#calc-rec-press-unit', pressLabel);

                        const elRecPermTds = results.querySelector('#calc-rec-perm-tds');
                        if (elRecPermTds) elRecPermTds.innerText = data.recycle.permeate_tds_mg_l.toFixed(1);

                        const elBlendTds = results.querySelector('#calc-rec-blend-tds');
                        if (elBlendTds) elBlendTds.innerText = data.recycle.blended_feed_tds_mg_l.toFixed(0);

                        const elRecFlow = results.querySelector('#calc-rec-flow');
                        const recFlowConv = conversions.flow.fromBase(data.recycle.recycle_flow_m3h, currentUnits.flow);
                        if (elRecFlow) elRecFlow.innerText = recFlowConv.toFixed(1);
                        setR('#calc-rec-flow-unit', flowLabel);

                        const elBlendFlow = results.querySelector('#calc-rec-blend-flow');
                        const blendFlowConv = conversions.flow.fromBase(data.recycle.blended_feed_flow_m3h, currentUnits.flow);
                        if (elBlendFlow) elBlendFlow.innerText = blendFlowConv.toFixed(1);
                        setR('#calc-rec-blend-flow-unit', flowLabel);
                        
                        const warnBlock = results.querySelector('#calc-rec-warning');
                        const warnText = results.querySelector('#calc-rec-warning-text');
                        if (data.recycle.warning && warnBlock && warnText) {
                            warnBlock.style.display = 'block';
                            warnText.innerText = data.recycle.warning;
                        } else if (warnBlock) {
                            warnBlock.style.display = 'none';
                        }
                    } else {
                        if (recycleCard) recycleCard.style.display = 'none';
                    }

                    // Render Two-Pass Summary Panels
                    const twoPassCard = results.querySelector('#calc-two-pass-summary-card');
                    const singlePassCard = results.querySelector('#calc-single-pass-summary-card');
                    const twoPassContainer = results.querySelector('#calc-two-pass-summary-container');
                    
                    if (data.technology_train && data.technology_train.includes('2P-RO') && data.pass2_results) {
                        if (singlePassCard) singlePassCard.style.display = 'none';
                        if (twoPassContainer) twoPassContainer.style.display = 'flex';
                        if (twoPassCard) twoPassCard.style.display = 'block'; // Keep old card active if needed elsewhere
                        
                        const p2sum = data.pass2_results.summary;
                        const p1sum = data.pass1_results ? data.pass1_results.summary : {};

                        // Helper to safely write overview inner texts
                        const setT = (sel, val) => { const el = results.querySelector(sel); if (el) el.innerText = val; };
                        
                        const flowLabel = { 'm3/h': 'm³/h', 'm3/d': 'm³/d', 'gpm': 'gpm', 'gpd': 'gpd' }[currentUnits.flow] || 'm³/h';
                        const pressLabel = currentUnits.pressure;
                        
                        const p1Flow = conversions.flow.fromBase(p1sum.perm_flow || 0, currentUnits.flow);
                        const p1Press = conversions.pressure.fromBase(p1sum.feed_pressure_bar || 0, currentUnits.pressure);
                        const p2Flow = conversions.flow.fromBase(p2sum.perm_flow || 0, currentUnits.flow);
                        const p2Press = conversions.pressure.fromBase(p2sum.feed_pressure_bar || 0, currentUnits.pressure);
                        
                        // Pass 1 Overview Elements
                        setT('#calc-2p-p1-rec',          ((p1sum.total_recovery || 0) * 100).toFixed(1));
                        setT('#calc-2p-p1-flow-summary',  p1Flow.toFixed(1));
                        setT('#calc-2p-p1-press',        p1Press.toFixed(1));
                        setT('#calc-2p-p1-tds-summary',  (p1sum.perm_tds || 0).toFixed(2));
                        setT('#calc-2p-p1-sec',          (p1sum.sec_kwh_m3 || 0).toFixed(2));
                        
                        setT('#calc-2p-p1-flow-summary-unit', flowLabel);
                        setT('#calc-2p-p1-press-unit', pressLabel);

                        // Pass 2 Overview Elements
                        setT('#calc-2p-p2-rec',          (p2sum.total_recovery * 100).toFixed(1));
                        setT('#calc-2p-p2-flow-summary',  p2Flow.toFixed(1));
                        setT('#calc-2p-p2-press-summary', p2Press.toFixed(1));
                        setT('#calc-2p-p2-tds-summary',  p2sum.perm_tds.toFixed(2));
                        setT('#calc-2p-p2-sec',          p2sum.sec_kwh_m3.toFixed(2));
                        setT('#calc-2p-p2-pump',         (p2sum.hp_pump_power_kw || 0).toFixed(1));
                        
                        setT('#calc-2p-p2-flow-summary-unit', flowLabel);
                        setT('#calc-2p-p2-press-summary-unit', pressLabel);

                        // Interstage Conditioning Element
                        const elCondDesc = results.querySelector('#calc-2p-cond-desc');
                        if (elCondDesc) {
                            if (data.conditioning && data.conditioning.enabled) {
                                elCondDesc.innerText = `${data.conditioning.chemical || 'Chemical'} to pH ${data.conditioning.target_ph || '9.8'}${data.conditioning.dose_mg_l ? ' (' + data.conditioning.dose_mg_l.toFixed(1) + ' mg/L)' : ''}`;
                            } else {
                                elCondDesc.innerText = 'Disabled';
                            }
                        }
                    } else {
                        if (singlePassCard) singlePassCard.style.display = 'block';
                        if (twoPassContainer) twoPassContainer.style.display = 'none';
                    }

                    // Render Stage-wise & Element-wise Tables
                    const tbodyStage = results.querySelector('#calc-stage-tbody');
                    const tbodyHyd = results.querySelector('#calc-hyd-tbody');
                    
                    let stagesHtml = '';
                    let hydHtml = '';
                    
                    const processPass = (passData, passName, passPrefix) => {
                        if (!passData || !passData.stages) return;
                        
                        if (passPrefix) {
                            stagesHtml += `<tr style="background: var(--input-bg);"><td colspan="5" style="text-align: left; padding-left: 10px; font-weight: bold; color: var(--primary-color);">${passName}</td></tr>`;
                        }
                        
                        stagesHtml += passData.stages.map(s => {
                            const sf = conversions.flow.fromBase(s.feed_flow, currentUnits.flow);
                            const sp = conversions.flow.fromBase(s.perm_flow, currentUnits.flow);
                            const sc = conversions.flow.fromBase(s.conc_flow, currentUnits.flow);
                            return `
                            <tr class="stage-summary-row" data-stage="${passPrefix ? passPrefix + '-' : ''}${s.stage}" style="cursor: pointer;" onclick="toggleStageElements('${passPrefix ? passPrefix + '-' : ''}${s.stage}', this)">
                                <td style="text-align: left; font-weight: 600; padding-left: ${passPrefix ? '20px' : '10px'};"><i class="fa-solid fa-chevron-right" id="stage-chevron-${passPrefix ? passPrefix + '-' : ''}${s.stage}" style="margin-right: 0.5rem; color: var(--primary-color); transition: transform 0.2s; transform: rotate(0deg);"></i> Stage ${s.stage}</td>
                                <td>${sf.toFixed(2)}</td>
                                <td>${sp.toFixed(2)}</td>
                                <td>${sc.toFixed(2)}</td>
                                <td>${(s.recovery * 100).toFixed(1)}%</td>
                            </tr>
                        `}).join('');
                        
                        if (passData.elements && passData.summary) {
                            const vesselsPerStage = passData.summary.vessels_per_stage || [];
                            for (let stageIdx = 0; stageIdx < vesselsPerStage.length; stageIdx++) {
                                const stageElements = passData.elements.filter(e => e.stage === (stageIdx + 1));
                                
                                hydHtml += stageElements.map(e => {
                                    const ef = conversions.flow.fromBase(e.feed_flow, currentUnits.flow);
                                    const ep = conversions.flow.fromBase(e.perm_flow, currentUnits.flow);
                                    const ec = conversions.flow.fromBase(e.conc_flow, currentUnits.flow);
                                    const epress = conversions.pressure.fromBase(e.feed_pressure, currentUnits.pressure);
                                    const edp = conversions.pressure.fromBase(e.dp, currentUnits.pressure);
                                    const eflux = conversions.flux ? conversions.flux.fromBase(e.flux, currentUnits.flux || 'LMH') : e.flux;
                                    return `
                                    <tr class="stage-row-${passPrefix ? passPrefix + '-' : ''}${e.stage}" style="display: none;">
                                        <td>${passPrefix === 'P2' ? 'P2-' : ''}S${e.stage}-E${e.position}</td>
                                        <td>${ef.toFixed(2)}</td>
                                        <td>${ep.toFixed(3)}</td>
                                        <td>${ec.toFixed(2)}</td>
                                        <td>${epress.toFixed(1)}</td>
                                        <td>${edp.toFixed(2)}</td>
                                        <td>${eflux.toFixed(1)}</td>
                                        <td>${(e.recovery * 100).toFixed(1)}</td>
                                        <td>${e.beta.toFixed(2)}</td>
                                    </tr>
                                `}).join('');
                            }
                        }
                    };
                    
                    const currentTrain = document.getElementById('calc-tech-train').value;
                    if (currentTrain.includes('2P-RO') && data.pass1_results && data.pass2_results) {
                        processPass(data.pass1_results, "Pass 1 (Primary RO)", "P1");
                        processPass(data.pass2_results, "Pass 2 (Secondary RO)", "P2");
                    } else {
                        processPass(data.ro_results, "", "");
                    }
                    
                    if (tbodyStage) tbodyStage.innerHTML = stagesHtml;
                    if (tbodyHyd) tbodyHyd.innerHTML = hydHtml;
                    
                    const dynFlowLabel = { 'm3/h': 'm³/h', 'm3/d': 'm³/d', 'gpm': 'gpm', 'gpd': 'gpd' }[currentUnits.flow] || 'm³/h';
                    const dynPressLabel = currentUnits.pressure;
                    const dynFluxLabel = currentUnits.flux || 'LMH';

                    ['calc-stage-feed-flow-unit', 'calc-stage-perm-flow-unit', 'calc-stage-conc-flow-unit', 
                     'calc-hyd-feed-flow-unit', 'calc-hyd-perm-flow-unit', 'calc-hyd-conc-flow-unit'].forEach(id => {
                        const el = document.getElementById(id);
                        if (el) el.innerText = `(${dynFlowLabel})`;
                     });
                     
                    ['calc-hyd-feed-press-unit', 'calc-hyd-deltap-unit'].forEach(id => {
                        const el = document.getElementById(id);
                        if (el) el.innerText = `(${dynPressLabel})`;
                    });
                    
                    const fUnitEl = document.getElementById('calc-hyd-flux-unit');
                    if (fUnitEl) fUnitEl.innerText = `(${dynFluxLabel})`;

                    // Render Booster Pumps
                    const bpCard = results.querySelector('#calc-booster-pumps-card');
                    const tbodyBP = results.querySelector('#calc-booster-pumps-tbody');
                    if (data.ro_results && data.ro_results.booster_pumps && data.ro_results.booster_pumps.length > 0) {
                        const requiredPumps = data.ro_results.booster_pumps.filter(bp => bp.required);
                        if (requiredPumps.length > 0) {
                            if (bpCard) bpCard.style.display = 'block';
                            if (tbodyBP) tbodyBP.innerHTML = requiredPumps.map(bp => {
                                const bpFlow = conversions.flow.fromBase(bp.flow_m3h, currentUnits.flow);
                                const bpInlet = conversions.pressure.fromBase(bp.inlet_pressure_bar, currentUnits.pressure);
                                const bpOutlet = conversions.pressure.fromBase(bp.outlet_pressure_bar, currentUnits.pressure);
                                const bpDP = conversions.pressure.fromBase(bp.boost_dp_bar, currentUnits.pressure);
                                return `
                                <tr>
                                    <td style="text-align: left;"><i class="fa-solid fa-arrow-right" style="color: var(--primary-color); margin-right: 0.5rem;"></i>${bp.location}</td>
                                    <td>${bpFlow.toFixed(1)}</td>
                                    <td>${bpInlet.toFixed(1)} → ${bpOutlet.toFixed(1)}</td>
                                    <td><strong>+${bpDP.toFixed(1)}</strong></td>
                                    <td>${bp.power_kw.toFixed(2)}</td>
                                </tr>
                            `}).join('');
                            
                            const bpSet = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
                            bpSet('calc-bp-flow-unit', `(${dynFlowLabel})`);
                            bpSet('calc-bp-inlet-press-unit', `(${dynPressLabel})`);
                            bpSet('calc-bp-dp-unit', `(${dynPressLabel})`);
                        } else {
                            if (bpCard) bpCard.style.display = 'none';
                        }
                    } else {
                        if (bpCard) bpCard.style.display = 'none';
                    }
                    
                    // Render Ion Rejection Table
                    const tbodyIon = results.querySelector('#calc-ion-tbody');
                    let ionsHtml = '';
                    const ionMap = { 'Ca': 'calcium', 'Mg': 'magnesium', 'Na': 'sodium', 'K': 'potassium', 'Ba': 'barium', 'Sr': 'strontium', 'Cl': 'chloride', 'SO4': 'sulfate', 'HCO3': 'bicarbonate', 'NO3': 'nitrate', 'F': 'fluoride', 'SiO2': 'silica', 'B': 'boron', 'PO4': 'phosphate', 'NH4': 'ammonium', 'Al': 'aluminium', 'Fe': 'iron', 'Mn': 'manganese' };
                    
                    let activeRes = data.ro_results || data.pass2_results || data.pass1_results;
                    let activeSum = activeRes ? activeRes.summary : null;
                    
                    if (activeSum && activeSum.conc_ions) {
                        for (const [ion, feedC] of Object.entries(activeSum.conc_ions)) { // just to get keys
                            const f = activeSum.feed_tds > 0 ? (payload.feed_water[ionMap[ion]] || 0) : 0;
                            let p = activeSum.perm_ions[ion] || 0;
                            let c = activeSum.conc_ions[ion] || 0;
                        let rej = 0;
                        if (f > 0) {
                            rej = (1 - (p / f)) * 100;
                        } else {
                            // If feed is physically 0, override solver trace values to show clean 0s
                            p = 0;
                            c = 0;
                            rej = 0;
                        }
                        
                        ionsHtml += `
                            <tr>
                                <td style="text-align:left;">${ion}</td>
                                <td>${f.toFixed(2)}</td>
                                <td>${p.toFixed(3)}</td>
                                <td>${c.toFixed(2)}</td>
                                <td>${rej.toFixed(2)}</td>
                            </tr>
                        `;
                        }
                    }
                    if (tbodyIon) tbodyIon.innerHTML = ionsHtml;

                    // ── Render PHREEQC Concentrate Scaling Risks ──────────────
                    const siCard  = results.querySelector('#calc-si-card');
                    const siTbody = results.querySelector('#calc-si-tbody');
                    const siData  = data.concentrate_si;
                    const siPh   = data.concentrate_ph;

                    if (siData && siCard) {
                        siCard.style.display = 'block';

                        // Thresholds: { mod, high, crit } — lower bound triggers each tier
                        const SI_LIMITS = {
                            'Calcite':   { mod: 0.0,  high: 0.5, crit: 1.0,  formula: 'CaCO₃',       rec_mod: 'Acid dosing or antiscalant recommended.', rec_high: 'Antiscalant dosing required.', rec_crit: 'Critical: reduce recovery or use strong acid/antiscalant.' },
                            'Aragonite': { mod: 0.0,  high: 0.5, crit: 1.0,  formula: 'CaCO₃ (orth.)',rec_mod: 'Carbonate scaling risk.', rec_high: 'Antiscalant dosing required.', rec_crit: 'Critical: carbonate scaling very likely.' },
                            'Dolomite':  { mod: 0.0,  high: 1.0, crit: 2.0,  formula: 'CaMg(CO₃)₂',  rec_mod: 'Monitor dolomite saturation.', rec_high: 'Antiscalant recommended.', rec_crit: 'Severe dolomite scaling risk.' },
                            'Gypsum':    { mod: 0.0,  high: 0.3, crit: 0.5,  formula: 'CaSO₄·2H₂O',  rec_mod: 'Antiscalant recommended.', rec_high: 'Antiscalant required — reduce recovery if possible.', rec_crit: 'Critical: Gypsum scale likely even with antiscalant.' },
                            'Anhydrite': { mod: 0.0,  high: 0.3, crit: 0.5,  formula: 'CaSO₄',        rec_mod: 'Antiscalant recommended.', rec_high: 'Antiscalant required.', rec_crit: 'Critical: reduce recovery.' },
                            'Barite':    { mod: -0.2, high: 0.0, crit: 0.3,  formula: 'BaSO₄',        rec_mod: 'Specialized antiscalant needed.', rec_high: 'Antiscalant required — Barite is very insoluble.', rec_crit: 'Critical: Barite scale almost certain without inhibitor.' },
                            'Celestite': { mod: 0.0,  high: 0.2, crit: 0.4,  formula: 'SrSO₄',        rec_mod: 'Specialized antiscalant recommended.', rec_high: 'Antiscalant required.', rec_crit: 'Critical: Celestite scaling likely.' },
                            'Fluorite':  { mod: 0.0,  high: 0.5, crit: 0.5,  formula: 'CaF₂',         rec_mod: 'Monitor fluoride-calcium balance.', rec_high: 'Antiscalant required.', rec_crit: 'Critical: Fluorite scaling risk.' },
                            'SiO2(a)':   { mod: -0.1, high: 0.0, crit: 0.2,  formula: 'SiO₂ (am.)',   rec_mod: 'Silica approaching saturation — pH adjustment or silica antiscalant.', rec_high: 'Silica antiscalant required.', rec_crit: 'Critical: Silica fouling very likely — reduce recovery.' },
                        };

                        const RISK_STYLES = {
                            'NONE':     { bg: 'rgba(16,185,129,0.15)', color: '#10b981', label: '✓ None' },
                            'LOW':      { bg: 'rgba(16,185,129,0.1)',  color: '#6ee7b7', label: '↗ Low' },
                            'MODERATE': { bg: 'rgba(251,191,36,0.15)', color: '#f59e0b', label: '⚠ Moderate' },
                            'HIGH':     { bg: 'rgba(249,115,22,0.15)', color: '#f97316', label: '⚠ High' },
                            'CRITICAL': { bg: 'rgba(239,68,68,0.15)',  color: '#ef4444', label: '✕ Critical' },
                        };

                        let siHtml = '';
                        for (const [mineral, siVal] of Object.entries(siData)) {
                            const lim = SI_LIMITS[mineral];
                            if (!lim) continue;
                            let risk = 'NONE';
                            let rec  = 'No action required.';
                            let displayVal = siVal.toFixed(3);
                            
                            if (siVal <= -99) {
                                displayVal = '--';
                                rec = 'Constituent ions not present.';
                            } else if (siVal > lim.crit) { risk = 'CRITICAL'; rec = lim.rec_crit; }
                            else if (siVal > lim.high)   { risk = 'HIGH';     rec = lim.rec_high; }
                            else if (siVal > lim.mod)    { risk = 'MODERATE'; rec = lim.rec_mod; }
                            else if (siVal > lim.mod - 0.2) { risk = 'LOW'; rec = 'Monitor. No immediate action required.'; }

                            const rs = RISK_STYLES[risk];
                            siHtml += `
                                <tr>
                                    <td style="text-align:left; font-weight:600;">${mineral}</td>
                                    <td style="color:var(--text-secondary); font-size:0.8rem;">${lim.formula}</td>
                                    <td style="font-weight:700; color:${siVal > 0 ? (risk === 'CRITICAL' ? '#ef4444' : risk === 'HIGH' ? '#f97316' : '#f59e0b') : 'var(--text-secondary)'};">${displayVal}</td>
                                    <td><span style="font-size:0.72rem; font-weight:700; color:${rs.color};">${rs.label}</span></td>
                                </tr>`;
                        }

                        // Add Concentrate pH row at the bottom
                        if (siPh != null) {
                            siHtml += `
                                <tr>
                                    <td style="text-align:left; font-weight:600; padding-top: 1rem;">Concentrate pH</td>
                                    <td style="color:var(--text-secondary); font-size:0.8rem; padding-top: 1rem;">Equilibrium H⁺</td>
                                    <td style="font-weight:700; color:var(--text-secondary); padding-top: 1rem;">${siPh.toFixed(2)}</td>
                                    <td style="padding-top: 1rem;"><span style="font-size:0.72rem; font-weight:700; color:#3b82f6;">Computed</span></td>
                                </tr>
                            `;
                        }

                        if (siTbody) siTbody.innerHTML = siHtml;
                    } else {
                        if (siCard) siCard.style.display = 'none';
                    }
                    
                    // Render Warnings
                    let allWarnings = [];
                    if (data.uf_results && data.uf_results.warnings) allWarnings = allWarnings.concat(data.uf_results.warnings);
                    if (data.ro_results && data.ro_results.warnings) allWarnings = allWarnings.concat(data.ro_results.warnings);
                    allWarnings = allWarnings.filter(w => !w.type || !w.type.includes('Concentration Polarization'));
                    
                    const warnCard = results.querySelector('#calc-warnings-card');
                    const warnBody = results.querySelector('#calc-warnings-tbody');
                    if (allWarnings.length > 0) {
                        if (warnCard) warnCard.style.display = 'flex';
                        if (warnBody) warnBody.innerHTML = allWarnings.map(w => {
                            const st = w.status || 'WARNING';
                            const isFail = st === 'FAIL' || st === 'ERROR';
                            const color = isFail ? 'var(--error-color)' : 'var(--warning-color)';
                            const icon = isFail ? 'xmark' : 'triangle-exclamation';
                            return `
                            <tr>
                                <td style="text-align:left; color:${color};">
                                    <i class="fa-solid fa-${icon}"></i> ${w.type}
                                </td>
                                <td style="text-align:center;">${w.limit !== undefined ? w.limit : '-'}</td>
                                <td style="text-align:center;">${w.value !== undefined ? w.value.toFixed(2) : (w.estimate !== undefined ? w.estimate.toFixed(2) : '-')}</td>
                                <td style="text-align:center;"><span style="padding:0.2rem 0.5rem; border-radius:4px; font-size:0.7rem; background:${color}; color:white;">${st}</span></td>
                            </tr>
                            `;
                        }).join('');
                    } else {
                        if (warnCard) warnCard.style.display = 'flex';
                        if (warnBody) warnBody.innerHTML = `
                            <tr>
                                <td colspan="4" style="text-align:center; color:var(--success-color); padding: 1.5rem; font-weight: 500;">
                                    <i class="fa-solid fa-check-circle" style="margin-right: 0.5rem;"></i> No design warnings
                                </td>
                            </tr>
                        `;
                    }
                }
                
                // Reset active subtab (preserve current active subtab if any, otherwise default to overview)
                let activeTab = 'overview';
                const activeBtn = results.querySelector('.menu-bar .menu-btn.active');
                if (activeBtn) {
                    const onclickStr = activeBtn.getAttribute('onclick') || '';
                    const match = onclickStr.match(/switchCalcSubTab\(['"]([^'"]+)['"]/);
                    if (match) activeTab = match[1];
                }
                
                // Automatically switch to physics tab if the user ran a physics projection
                if (isPhysics) {
                    activeTab = 'physics';
                }
                
                switchCalcSubTab(activeTab);
                
                // Draw PFD
                try {
                    const p1ArrText = document.getElementById('calc-vessels-array').value;
                    const p1Arr = p1ArrText ? p1ArrText.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n) && n > 0) : [];
                    const nEl = parseInt(document.getElementById('calc-elements-pv').value) || 6;
                    window.drawPFDSVG(data.ro_results, p1Arr, nEl);
                } catch(e) {
                    console.error("PFD generation failed:", e);
                }
                
                loading.style.display = 'none';
                
                // Show report button
                results.style.display = 'flex';
                results.style.opacity = '1';
                
                // Clone the results to the report tab
                const reportContainer = document.getElementById('report-calculations-container');
                if (reportContainer) {
                    reportContainer.innerHTML = '<!-- Section 3: Detailed Calculations --><h3 style="margin-top: 0; border-bottom: 1px solid #e0e0e0; padding-bottom: 0.4rem; color: #0056b3; font-size: 0.9rem; font-weight: 700;"><i class="fa-solid fa-calculator"></i> Detailed Calculations</h3>' + results.innerHTML;
                    // Strip dark styling from cloned cards
                    const clonedCards = reportContainer.querySelectorAll('.card');
                    clonedCards.forEach(card => {
                        card.className = '';
                        card.style.marginBottom = '2.5rem';
                    });
                    const clonedHeaders = reportContainer.querySelectorAll('.card-header');
                    clonedHeaders.forEach(hdr => {
                        hdr.className = '';
                        hdr.style.borderBottom = '1px solid #e0e0e0';
                        hdr.style.marginBottom = '0.5rem';
                        hdr.style.paddingBottom = '0.2rem';
                        const title = hdr.querySelector('.card-title');
                        if (title) {
                            title.style.color = '#0056b3';
                            title.style.fontSize = '0.85rem';
                        }
                    });
                }

                runBtn.disabled = false;

                // Store last payload to generate report
                window.lastCalcPayload = payload;
                window.lastCalcPayload.ro_results = data.ro_results; // save results too for completeness
                if (data.physics_results) {
                    window.lastCalcPayload.physics_results = data.physics_results;
                    window.lastCalcPayload.physics_selected_year = data.physics_selected_year || 0;
                }

                // Show report button (if it was hidden somewhere)
                const oldReportBtn = document.getElementById('calc-report-btn');
                if (oldReportBtn) oldReportBtn.style.display = 'block';


            } catch (err) {
                console.error(err);
                alert("Error during calculation: " + err.message + "\nStack: " + err.stack);
                document.getElementById('calc-results-container').innerHTML = `<div style="color:red; padding: 2rem;"><h3>Calculation Error</h3><pre>${err.stack}</pre></div>`;
                document.getElementById('calc-results-container').style.display = 'block';
                if (window.hideLoader) window.hideLoader();
                runBtn.disabled = false;
            }
        });
    }

    const genReportBtn = document.getElementById('wave-report-generate-btn');
    const dlReportBtn = document.getElementById('wave-report-download-btn');
    
    if (dlReportBtn) {
        dlReportBtn.addEventListener('click', () => {
            if (!window.currentReportPdfUrl) return;
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = window.currentReportPdfUrl;
            a.download = 'PACE_Calculation_Report.pdf';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        });
    }

    if (genReportBtn) {
        genReportBtn.addEventListener('click', async () => {
            if (!window.lastCalcPayload) {
                alert("Please run a system calculation first before generating a report.");
                return;
            }
            
            const btnOriginalText = genReportBtn.innerHTML;
            genReportBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Generating...';
            genReportBtn.disabled = true;

            try {
                const pfdContainer = document.getElementById('pfd-svg-container');
                const svgEl = pfdContainer ? pfdContainer.querySelector('svg') : null;
                if (svgEl) {
                    try {
                        const serializer = new XMLSerializer();
                        let svgStr = serializer.serializeToString(svgEl);
                        if (!svgStr.match(/^<svg[^>]+xmlns="http\:\/\/www\.w3\.org\/2000\/svg"/)) {
                            svgStr = svgStr.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
                        }
                        const svgBlob = new Blob([svgStr], {type: 'image/svg+xml;charset=utf-8'});
                        const url = window.URL.createObjectURL(svgBlob);
                        
                        const canvas = document.createElement('canvas');
                        const w = svgEl.viewBox.baseVal ? svgEl.viewBox.baseVal.width : 800;
                        const h = svgEl.viewBox.baseVal ? svgEl.viewBox.baseVal.height : 400;
                        // Render at 3x scale for crisp PDF embedding
                        canvas.width = w * 3;
                        canvas.height = h * 3;
                        const ctx = canvas.getContext('2d');
                        ctx.fillStyle = '#ffffff';
                        ctx.fillRect(0, 0, canvas.width, canvas.height);
                        
                        const base64Data = await new Promise((resolve, reject) => {
                            const img = new Image();
                            img.onload = () => {
                                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                                resolve(canvas.toDataURL('image/png'));
                            };
                            img.onerror = (e) => reject(e);
                            img.src = url;
                        });
                        window.lastCalcPayload.pfd_png = base64Data;
                        window.lastCalcPayload.pfd_svg = null; // Don't use backend svglib
                        window.URL.revokeObjectURL(url);
                    } catch (err) {
                        console.error('Failed to rasterize SVG in browser:', err);
                        // Fallback to sending raw SVG to backend
                        window.lastCalcPayload.pfd_svg = svgEl.outerHTML;
                    }
                }

                // Filter out Concentration Polarization warnings from the report payload
                const payloadClone = JSON.parse(JSON.stringify(window.lastCalcPayload));
                if (payloadClone.ro_results && payloadClone.ro_results.warnings) {
                    payloadClone.ro_results.warnings = payloadClone.ro_results.warnings.filter(w => 
                        !w.type || !w.type.includes('Concentration Polarization')
                    );
                }
                payloadClone.units = window.currentUnits || {
                    flow: 'm3/h', pressure: 'bar', flux: 'LMH', temp: 'C'
                };
                
                const res = await fetch(API_BASE + '/api/generate-calculation-report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payloadClone)
                });
                
                if (!res.ok) {
                    const errText = await res.text();
                    throw new Error(`Failed to generate report: ${res.status} ${errText}`);
                }
                
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                
                // Store the url globally for the download button
                window.currentReportPdfUrl = url;
                
                // Show in the iframe
                const placeholder = document.getElementById('report-preview-placeholder');
                const iframe = document.getElementById('pdf-preview-iframe');
                if (placeholder && iframe) {
                    placeholder.style.display = 'none';
                    iframe.src = url;
                    iframe.style.display = 'block';
                }

                // Show the download button
                if (dlReportBtn) {
                    dlReportBtn.style.display = 'flex';
                }
                
            } catch (err) {
                console.error(err);
                alert("Error generating report: " + err.message);
            } finally {
                genReportBtn.innerHTML = btnOriginalText;
                genReportBtn.disabled = false;
            }
        });
    }
});

// Helper for currency formatting
window.formatINR = function(num) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 2
    }).format(num);
};

// Switch calculation module sub-tabs
window.switchCalcSubTab = function(tabName, event) {
    let container = document.getElementById('calc-results-container');
    if (event && event.currentTarget) {
        container = event.currentTarget.closest('#calc-results-container') || event.currentTarget.closest('#report-calculations-container') || container;
    }
    if (!container) return;
    
    const overview = container.querySelector('#calc-content-overview');
    const membrane = container.querySelector('#calc-content-membrane');
    const hydraulic = container.querySelector('#calc-content-hydraulic');
    const ion = container.querySelector('#calc-content-ion');
    const economics = container.querySelector('#calc-content-economics');
    const pfd = container.querySelector('#calc-content-pfd');
    
    const physics = container.querySelector('#calc-content-physics');
    if (overview) overview.style.display = 'none';
    if (membrane) membrane.style.display = 'none';
    if (hydraulic) hydraulic.style.display = 'none';
    if (ion) ion.style.display = 'none';
    if (economics) economics.style.display = 'none';
    if (pfd) pfd.style.display = 'none';
    if (physics) physics.style.display = 'none';
    
    const menuBar = container.querySelector('.menu-bar');
    if (menuBar) {
        const btns = menuBar.querySelectorAll('.menu-btn');
        btns.forEach(b => b.classList.remove('active'));
    }
    
    if (tabName === 'overview' && overview) overview.style.display = 'flex';
    else if (tabName === 'membrane' && membrane) membrane.style.display = 'flex';
    else if (tabName === 'hydraulic' && hydraulic) hydraulic.style.display = 'block';
    else if (tabName === 'ion' && ion) ion.style.display = 'block';
    else if (tabName === 'economics' && economics) economics.style.display = 'flex';
    else if (tabName === 'physics' && physics) physics.style.display = 'flex';
    else if (tabName === 'pfd' && pfd) {
        pfd.style.display = 'flex';
        if (typeof window.updateLivePFD === 'function') {
            window.updateLivePFD();
        }
        // Give the container time to render, then re-measure for the PFD
        setTimeout(() => {
            const svg = pfd.querySelector('svg');
            if(svg) {
                const bcr = svg.getBoundingClientRect();
                svg.setAttribute('width', bcr.width);
            }
        }, 50);
    }
    
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('active');
    }
};

// Toggle element rows visibility when clicking on a stage summary row
window.toggleStageElements = function(stageNum, clickedRow) {
    // Determine the active container (either Calculation tab or Report tab)
    const container = clickedRow.closest('#calc-results-container') || clickedRow.closest('#report-calculations-container') || document;
    
    const rows = container.querySelectorAll(`.stage-row-${stageNum}`);
    const chevron = clickedRow.querySelector(`.fa-chevron-right`) || clickedRow.querySelector(`#stage-chevron-${stageNum}`);
    if (rows.length === 0) return;
    
    const isCollapsed = rows[0].style.display === 'none';
    
    rows.forEach(row => {
        row.style.display = isCollapsed ? 'table-row' : 'none';
    });
    
    if (chevron) {
        chevron.style.transform = isCollapsed ? 'rotate(90deg)' : 'rotate(0deg)';
    }
};


// ── PFD SVG Engine ────────────────────────────────────────────────────────────
window.exportPFDSVG = function() {
    const el = document.getElementById('pfd-svg');
    if (!el) return;
    
    const style = getComputedStyle(document.body);
    const vars = ['--card-bg', '--input-bg', '--card-border', '--text-primary', '--text-secondary', '--input-border',
                  '--perm-tank-bg', '--perm-tank-stroke', '--perm-tank-text',
                  '--rej-tank-bg', '--rej-tank-stroke', '--rej-tank-text',
                  '--feed-tank-bg', '--feed-tank-stroke', '--feed-tank-text'];
    let cssBlock = ':root {\n';
    vars.forEach(v => {
        cssBlock += `  ${v}: ${style.getPropertyValue(v).trim()};\n`;
    });
    cssBlock += '}';
    
    const clone = el.cloneNode(true);
    const styleEl = document.createElement('style');
    styleEl.textContent = cssBlock;
    clone.insertBefore(styleEl, clone.firstChild);
    
    const blob = new Blob([clone.outerHTML], {type: 'image/svg+xml'});
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = 'Process_Flow_Diagram.svg'; a.click();
    URL.revokeObjectURL(url);
};

window.drawPFDSVG = function(ro_results, p1Arr, nEl) {
    if (!p1Arr || p1Arr.length === 0) {
        const containers = document.querySelectorAll('#pfd-svg-container');
        const emptyMsg = '<div style="display:flex; justify-content:center; align-items:center; height:300px; color:#64748b; font-size:1.1rem; font-weight:600; width:100%;">Incomplete Information for PFD</div>';
        containers.forEach(c => {
            c.innerHTML = emptyMsg;
            c.style.background = 'transparent';
            c.style.boxShadow = 'none';
        });
        return;
    }
    const stages_data = (ro_results && ro_results.stages) ? ro_results.stages : [];
    
    let sys_feed_flow = (stages_data.length > 0) ? stages_data[0].feed_flow : 0;
    if (sys_feed_flow === 0) {
        const flowInput = document.getElementById('flow');
        if (flowInput) sys_feed_flow = parseFloat(flowInput.value) || 0;
    }
    
    let overall_recovery = 75;
    const recInput = document.getElementById('recovery');
    if (recInput) overall_recovery = parseFloat(recInput.value) || 75;

    let p2Arr = [];
    const hasPass2 = !!(window.lastCalcResult && window.lastCalcResult.pass2_results);
    
    if (hasPass2) {
        const elP2Stages = document.getElementById('calc-pass2-stages');
        let np2 = elP2Stages ? parseInt(elP2Stages.value) || 1 : 1;
        for (let i = 1; i <= np2; i++) {
            const vi = document.getElementById('calc-pass2-vessels-s' + i);
            p2Arr.push(vi ? parseInt(vi.value) || 2 : 2);
        }
    }

    const passesArray = [p1Arr];
    if (hasPass2) passesArray.push(p2Arr);

    const state = {
        passes: passesArray,
        theme: {
            name: 'classic-pace',
            canvasBg: '#CEDDFF',
            vesselFill: '#FFFFF0',
            vesselStroke: '#000000',
            feed: '#555555',
            permeate: '#3B50D0',
            concentrate: '#C00000',
            pump: '#293990',
            label: '#000000'
        },
        geo: {
            vesselW: 110,
            vesselH: 32,
            vGap: 18,
            headerMargin: 26,
            manifoldMargin: 26,
            stageExitPad: 36,
            stageGap: 130,
            passGap: 72,
            passHeaderMargin: 50,
            feedStub: 80,
            outletStub: 50
        },
        animateFlow: false,
        calc: {
            feedFlow: sys_feed_flow,
            recovery: overall_recovery,
            showFlows: true
        }
    };

    // --- SVG Rendering Core ---
function buildSVG() {
  const COLORS = state.theme;
  const GEO = state.geo;
  const centerY = 320;
  
  let x = 60;
  let fullMarkup = '';
  let passExits = [];
  let sysMaxTop = centerY;
  let sysMaxBottom = centerY;
  let pumpsMarkup = '';

  // Arrow markers definition
  const arrowMarkerDefs = `
    <defs>
      <marker id="pfd-ah-feed" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
        <path d="M2 1 L8 5 L2 9 Z" fill="${COLORS.feed}" />
      </marker>
      <marker id="pfd-ah-permeate" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
        <path d="M2 1 L8 5 L2 9 Z" fill="${COLORS.permeate}" />
      </marker>
      <marker id="pfd-ah-concentrate" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
        <path d="M2 1 L8 5 L2 9 Z" fill="${COLORS.concentrate}" />
      </marker>
    </defs>
  `;

  // Draw high-pressure pump icon
  function pumpIcon(cx, cy, scale = 1, labelText = 'HP PUMP') {
    const isBooster = labelText === 'BOOSTER';
    
    let baseD = isBooster 
      ? "M -16 16 L -22 28 L 22 28 L 16 16 Z" 
      : "M -38 16 L -44 28 L 22 28 L 16 16 Z";
    
    let baseRectX = isBooster ? -24 : -46;
    let baseRectW = isBooster ? 48 : 70;
    
    let motorMarkup = '';
    if (!isBooster) {
      motorMarkup = `
        <!-- Motor housing -->
        <rect x="-42" y="-14" width="24" height="28" rx="3" fill="#2B3B98" stroke="#ffffff" stroke-width="2" />
        <!-- Cooling fins -->
        <line x1="-36" y1="-14" x2="-36" y2="14" stroke="#ffffff" stroke-width="1.5" />
        <line x1="-30" y1="-14" x2="-30" y2="14" stroke="#ffffff" stroke-width="1.5" />
        <line x1="-24" y1="-14" x2="-24" y2="14" stroke="#ffffff" stroke-width="1.5" />
        <!-- Motor coupling -->
        <rect x="-18" y="-6" width="6" height="12" fill="#2B3B98" stroke="#ffffff" stroke-width="2" />
      `;
    }

    const textX = isBooster ? 0 : -11;

    return `
      <g class="pfd-pump" transform="translate(${cx},${cy}) scale(${scale})" cursor="pointer" data-type="pump" data-name="${labelText}">
        <!-- Base -->
        <path d="${baseD}" fill="#2B3B98" stroke="#ffffff" stroke-width="2" stroke-linejoin="round" />
        <rect x="${baseRectX}" y="28" width="${baseRectW}" height="4" fill="#2B3B98" stroke="#ffffff" stroke-width="2" />
        
        ${motorMarkup}
        
        <!-- Volute & Discharge Path -->
        <path d="M 30 -18 L 0 -18 A 18 18 0 1 0 16.1 -8 L 30 -8 Z" fill="#2B3B98" stroke="#ffffff" stroke-width="2" stroke-linejoin="round" />
        
        <!-- Discharge Flange -->
        <rect x="30" y="-21" width="6" height="16" fill="#2B3B98" stroke="#ffffff" stroke-width="2" />
        
        <!-- Inner Motor / Suction Eye -->
        <circle cx="0" cy="0" r="8" fill="#2B3B98" stroke="#ffffff" stroke-width="2" />
        
        <!-- Text label -->
        <text x="${textX}" y="44" font-size="11" font-weight="700" fill="${COLORS.label}" text-anchor="middle" font-family="Outfit, sans-serif">${labelText}</text>
      </g>
    `;
  }

  // Draw mixer icon
  function mixerIcon(cx, cy, scale = 1) {
    return `
      <g class="pfd-mixer" transform="translate(${cx},${cy}) scale(${scale})" cursor="pointer" data-type="mixer">
        <circle cx="0" cy="0" r="10" fill="#FFFFF0" stroke="${COLORS.vesselStroke}" stroke-width="2" />
        <line x1="-7" y1="-7" x2="7" y2="7" stroke="${COLORS.vesselStroke}" stroke-width="2" />
        <line x1="-7" y1="7" x2="7" y2="-7" stroke="${COLORS.vesselStroke}" stroke-width="2" />
      </g>
    `;
  }

  // Draw vessel shape
  function vesselShape(vx, vy, vw, vh, passIdx, stageIdx, vesselIdx) {
    const midY = vy + vh / 2;
    const label = `PV #${vesselIdx + 1}`;
    
    // Construct the outer shell path
    const p1x = vx, p1y = vy;
    const p2x = vx + 10, p2y = vy;
    const p3x = vx + 16, p3y = vy + 4;
    const p4x = vx + vw - 16, p4y = vy + 4;
    const p5x = vx + vw - 10, p5y = vy;
    const p6x = vx + vw, p6y = vy;
    const p7x = vx + vw, p7y = vy + vh;
    const p8x = vx + vw - 10, p8y = vy + vh;
    const p9x = vx + vw - 16, p9y = vy + vh - 4;
    const p10x = vx + 16, p10y = vy + vh - 4;
    const p11x = vx + 10, p11y = vy + vh;
    const p12x = vx, p12y = vy + vh;

    const pathD = `M ${p1x} ${p1y} L ${p2x} ${p2y} L ${p3x} ${p3y} L ${p4x} ${p4y} L ${p5x} ${p5y} L ${p6x} ${p6y} L ${p7x} ${p7y} L ${p8x} ${p8y} L ${p9x} ${p9y} L ${p10x} ${p10y} L ${p11x} ${p11y} L ${p12x} ${p12y} Z`;

    let s = `
      <g class="pfd-vessel" data-pass="${passIdx}" data-stage="${stageIdx}" data-vessel="${vesselIdx}">
        <path d="${pathD}" fill="${COLORS.vesselFill}" stroke="${COLORS.vesselStroke}" stroke-width="1.5" stroke-linejoin="round" />
        
        <!-- Vertical lines for end caps -->
        <line x1="${p2x}" y1="${p2y}" x2="${p11x}" y2="${p11y}" stroke="${COLORS.vesselStroke}" stroke-width="1.5" />
        <line x1="${p5x}" y1="${p5y}" x2="${p8x}" y2="${p8y}" stroke="${COLORS.vesselStroke}" stroke-width="1.5" />
        
        <!-- Diagonal membrane line (top-left to bottom-right) -->
        <line x1="${p3x}" y1="${p3y}" x2="${p9x}" y2="${p9y}" stroke="${COLORS.vesselStroke}" stroke-width="2.5" />
        
        <!-- Label with background to mask the diagonal line -->
        <rect x="${vx + vw / 2 - 20}" y="${midY - 8}" width="40" height="16" fill="${COLORS.vesselFill}" />
        <text x="${vx + vw / 2}" y="${midY + 4}" font-size="11" fill="${COLORS.label}" font-weight="600" text-anchor="middle" font-family="Inter, sans-serif" pointer-events="none">${label}</text>
      </g>
    `;
    return s;
  }

  // Create stream paths (orthogonal routing) for animations
  function streamPath(points, color, flowClass = '', addMarker = false) {
    if (points.length < 2) return '';
    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      d += ` L ${points[i].x} ${points[i].y}`;
    }
    const animClass = state.animateFlow ? 'flow-animating' : '';
    let markerAttr = '';
    if (addMarker) {
      if (color === COLORS.feed) markerAttr = 'marker-end="url(#pfd-ah-feed)"';
      else if (color === COLORS.permeate) markerAttr = 'marker-end="url(#pfd-ah-permeate)"';
      else if (color === COLORS.concentrate) markerAttr = 'marker-end="url(#pfd-ah-concentrate)"';
    }
    return `<path d="${d}" stroke="${color}" fill="none" stroke-width="2" class="stream-path ${animClass} ${flowClass}" ${markerAttr} />`;
  }

  // Linear calculations model values
  const Q_f = state.calc.feedFlow;
  const Y_overall = state.calc.recovery / 100;
  
  // Calculate flow rates per pass
  // Assuming Pass 1 recovery = Y_overall, Pass 2 recovery = 0.85
  const passFlows = [];
  let currentFeed = Q_f;
  
  state.passes.forEach((stages, pi) => {
    const passRec = pi === 0 ? Y_overall : 0.85; // Pass 2+ is treated as 2nd pass polishing
    const passPerm = currentFeed * passRec;
    const passConc = currentFeed - passPerm;
    
    // Stage recovery distribution: 1 - (1-Y_pass)^(1/k)
    const k = stages.length;
    const stageRec = 1 - Math.pow(1 - passRec, 1 / k);
    
    const stageFlows = [];
    let stageFeed = currentFeed;
    
    stages.forEach((v, si) => {
      const stagePerm = stageFeed * stageRec;
      const stageConc = stageFeed - stagePerm;
      stageFlows.push({
        feed: stageFeed,
        permeate: stagePerm,
        concentrate: stageConc
      });
      stageFeed = stageConc; // Next stage feed is current stage concentrate
    });
    
    passFlows.push({
      feed: currentFeed,
      permeate: passPerm,
      concentrate: passConc,
      stages: stageFlows
    });
    
    currentFeed = passPerm; // Double pass: 2nd pass feed is 1st pass permeate
  });

  let hasUF = false;
  const trainSelect = document.getElementById('calc-tech-train');
  if (trainSelect) {
      hasUF = trainSelect.value.includes('UF');
  } else if (window.lastCalcPayload && window.lastCalcPayload.technology_train) {
      hasUF = window.lastCalcPayload.technology_train.includes('UF');
  }

  let ufShift = hasUF ? 80 : 0;

  // Render main inlet stream with offset for pump suction/discharge
  const pumpCy = centerY + 13;
  const pumpCx = x + GEO.feedStub + 34 + ufShift;
  
  const mixCx = x - 10;
  const mixCy = pumpCy;

  // The pump casing extends to pumpCx + 36. We place the start of the manifold (x) well past it.
  const newX = pumpCx + 90;
  const feedInXFirst = newX - GEO.manifoldMargin;

  // Raw feed into mixer (stops at left edge of circle)
  fullMarkup += streamPath([{ x: mixCx - 40, y: pumpCy }, { x: mixCx - 10, y: pumpCy }], COLORS.feed, '', true);
  
  let ufMarkup = '';
  if (hasUF) {
      const ufCx = (mixCx + 10 + pumpCx - 46) / 2;
      const ufCy = pumpCy;
      
      // Draw UF Module Box
      ufMarkup += `
        <g transform="translate(${ufCx},${ufCy})">
          <rect x="-24" y="-24" width="48" height="48" fill="#f8fafc" stroke="#334155" stroke-width="2" rx="4"/>
          <text x="0" y="4" font-size="14" font-weight="800" fill="#334155" text-anchor="middle" font-family="Outfit, sans-serif">UF</text>
          <text x="0" y="16" font-size="8" font-weight="600" fill="#64748b" text-anchor="middle" font-family="Outfit, sans-serif">Pre-treat</text>
        </g>
      `;
      // Path from mixer to UF
      fullMarkup += streamPath([{ x: mixCx + 10, y: pumpCy }, { x: ufCx - 24, y: pumpCy }], COLORS.feed, '', true);
      // Path from UF to Pump
      fullMarkup += streamPath([{ x: ufCx + 24, y: pumpCy }, { x: pumpCx - 46, y: pumpCy }], COLORS.feed, '', true);
  } else {
      // Mixed line from mixer to suction (starts at right edge of circle, stops at left edge of pump motor)
      fullMarkup += streamPath([{ x: mixCx + 10, y: pumpCy }, { x: pumpCx - 46, y: pumpCy }], COLORS.feed, '', true);
  }
  
  // Line out of discharge (top)
  fullMarkup += streamPath([{ x: pumpCx, y: centerY }, { x: feedInXFirst, y: centerY }], COLORS.feed);
  
  fullMarkup += `<text x="${mixCx - 36}" y="${pumpCy - 8}" font-size="11" font-weight="600" fill="${COLORS.label}" font-family="Outfit, sans-serif">Feed</text>`;
  
  if (state.calc.showFlows) {
    fullMarkup += `<text x="${mixCx - 36}" y="${pumpCy + 16}" font-size="9" font-weight="500" fill="${COLORS.feed}" font-family="Fira Code, monospace">${Q_f.toFixed(1)} m³/h</text>`;
  }

  pumpsMarkup += mixerIcon(mixCx, mixCy, 1);
  pumpsMarkup += ufMarkup;
  // Draw main feed pump (added to pumpsMarkup to render on top of the flow line)
  pumpsMarkup += pumpIcon(pumpCx, pumpCy, 1, 'FEED PUMP');
  
  x = newX;

  // Render each pass
  state.passes.forEach((passStages, pi) => {
    const passFlow = passFlows[pi];
    const maxVesselsInPass = Math.max(...passStages.map(v => v > 4 ? 4 : v));
    const passHeight = maxVesselsInPass * GEO.vesselH + (maxVesselsInPass - 1) * GEO.vGap;
    const firstStageStartY = centerY - passHeight / 2;
    
    fullMarkup += `
      <g transform="translate(${x}, ${firstStageStartY - GEO.headerMargin - GEO.passHeaderMargin})">
        <text x="0" y="0" font-size="13" font-weight="800" fill="${COLORS.label}" font-family="Outfit, sans-serif">PASS ${pi + 1}</text>
        <line x1="0" y1="4" x2="54" y2="4" stroke="${COLORS.label}" stroke-width="2" />
      </g>
    `;

    let stageX = x;
    let feedFromX = stageX - 26;
    let feedFromY = centerY;
    let stagePermExits = [];
    let lastConcExit = null;
    let passMaxTop = centerY;
    let passMaxBottom = centerY;

    passStages.forEach((stageVessels, si) => {
      const stageFlow = passFlow.stages[si];
      const feedColor = si === 0 ? (pi === 0 ? COLORS.feed : COLORS.permeate) : COLORS.concentrate;
      const permHeaderY = firstStageStartY - GEO.headerMargin;
      const concManifoldY = Math.max(firstStageStartY + passHeight + GEO.manifoldMargin, centerY + 80);
      const stageExitX = stageX + GEO.vesselW + 30 + GEO.stageExitPad;

      passMaxTop = Math.min(passMaxTop, permHeaderY);
      passMaxBottom = Math.max(passMaxBottom, concManifoldY);

      fullMarkup += `<text x="${stageX + GEO.vesselW / 2}" y="${firstStageStartY - 14}" font-size="11" font-weight="700" fill="${COLORS.label}" text-anchor="middle" font-family="Outfit, sans-serif">Stage ${si + 1}</text>`;

      const feedInX = stageX - 26;
      if (si === 0) {
        fullMarkup += streamPath([{ x: feedFromX, y: feedFromY }, { x: feedInX, y: centerY }], feedColor);
      } else {
        const upX = feedFromX + 20;
        const pumpCy = centerY + 13;
        const pumpCx = upX + 34;
        
        fullMarkup += streamPath([
          { x: feedFromX, y: feedFromY },
          { x: upX, y: feedFromY },
          { x: upX, y: pumpCy },
          { x: pumpCx - 18, y: pumpCy }
        ], feedColor, '', true);
        
        fullMarkup += streamPath([
          { x: pumpCx, y: centerY },
          { x: feedInX, y: centerY }
        ], feedColor);
        
        pumpsMarkup += pumpIcon(pumpCx, pumpCy, 1, 'BOOSTER');
        
        if (state.calc.showFlows) {
          fullMarkup += `<text x="${upX + 4}" y="${pumpCy - 6}" font-size="8.5" font-weight="500" fill="${COLORS.concentrate}" font-family="Fira Code, monospace">${stageFlow.feed.toFixed(1)}</text>`;
        }
      }

      const displayCount = stageVessels > 4 ? 4 : stageVessels;
      let renderSlots = [];
      if (stageVessels <= 4) {
        for (let i=0; i<stageVessels; i++) renderSlots.push({ type: 'vessel', labelIdx: i });
      } else {
        renderSlots.push({ type: 'vessel', labelIdx: 0 });
        renderSlots.push({ type: 'vessel', labelIdx: 1 });
        renderSlots.push({ type: 'dots' });
        renderSlots.push({ type: 'vessel', labelIdx: stageVessels - 1 });
      }

      let pYs = [];
      let cYs = [];
      
      let feedMinY = centerY;
      let feedMaxY = centerY;

      renderSlots.forEach((slot, vi) => {
        const vy = firstStageStartY + vi * (GEO.vesselH + GEO.vGap);
        const vyMid = vy + GEO.vesselH / 2;
        
        feedMinY = Math.min(feedMinY, vyMid);
        feedMaxY = Math.max(feedMaxY, vyMid);

        if (slot.type === 'vessel') {
          fullMarkup += streamPath([{ x: feedInX, y: vyMid }, { x: stageX, y: vyMid }], feedColor, '', true);
          fullMarkup += vesselShape(stageX, vy, GEO.vesselW, GEO.vesselH, pi, si, slot.labelIdx);
          const pY = vy + GEO.vesselH * 0.25;
          const cY = vy + GEO.vesselH * 0.75;
          pYs.push(pY);
          cYs.push(cY);
          fullMarkup += streamPath([{ x: stageX + GEO.vesselW, y: pY }, { x: stageX + GEO.vesselW + 14, y: pY }], COLORS.permeate, '', true);
          fullMarkup += streamPath([{ x: stageX + GEO.vesselW, y: cY }, { x: stageX + GEO.vesselW + 30, y: cY }], COLORS.concentrate, '', true);
        } else if (slot.type === 'dots') {
          // Add a short feed stub pointing to the empty space for the dots
          fullMarkup += streamPath([{ x: feedInX, y: vyMid }, { x: stageX - 10, y: vyMid }], feedColor);
          fullMarkup += `<text x="${stageX + GEO.vesselW / 2}" y="${vyMid + 6}" font-size="24" font-weight="700" fill="${COLORS.label}" text-anchor="middle" font-family="Outfit, sans-serif">⋮</text>`;
        }
      });

      if (feedMinY < feedMaxY) {
        // Vertical feed distribution line
        fullMarkup += streamPath([{ x: feedInX, y: feedMinY }, { x: feedInX, y: feedMaxY }], feedColor);
      }

      const blueBusX = stageX + GEO.vesselW + 14;
      const redBusX = stageX + GEO.vesselW + 30;

      // Vertical collecting manifolds
      if (displayCount > 1) {
        fullMarkup += streamPath([{ x: blueBusX, y: pYs[0] }, { x: blueBusX, y: pYs[pYs.length - 1] }], COLORS.permeate);
        fullMarkup += streamPath([{ x: redBusX, y: cYs[0] }, { x: redBusX, y: cYs[cYs.length - 1] }], COLORS.concentrate);
      }
      
      const blueMergeY = (pYs[0] + pYs[pYs.length - 1]) / 2;
      const redMergeY = (cYs[0] + cYs[cYs.length - 1]) / 2;

      // Pipe to header/manifold exits
      fullMarkup += streamPath([
        { x: blueBusX, y: blueMergeY },
        { x: blueBusX, y: permHeaderY },
        { x: stageExitX, y: permHeaderY }
      ], COLORS.permeate);
      
      fullMarkup += streamPath([
        { x: redBusX, y: redMergeY },
        { x: redBusX, y: concManifoldY },
        { x: stageExitX, y: concManifoldY }
      ], COLORS.concentrate);

      stagePermExits.push({ x: stageExitX, y: permHeaderY });
      lastConcExit = { x: stageExitX, y: concManifoldY };

      // Flow indicators next to stage exit lines
      if (state.calc.showFlows) {
        fullMarkup += `<text x="${stageExitX - 22}" y="${permHeaderY - 6}" font-size="8.5" font-weight="600" fill="${COLORS.permeate}" font-family="Fira Code, monospace">${stageFlow.permeate.toFixed(1)}</text>`;
        fullMarkup += `<text x="${stageExitX - 22}" y="${concManifoldY + 12}" font-size="8.5" font-weight="600" fill="${COLORS.concentrate}" font-family="Fira Code, monospace">${stageFlow.concentrate.toFixed(1)}</text>`;
      }

      // Advance to next stage coordinate
      if (si < passStages.length - 1) {
        const nextX = stageExitX + GEO.stageGap;
        feedFromX = stageExitX;
        feedFromY = concManifoldY;
        stageX = nextX;
      } else {
        stageX = stageExitX;
      }
    });

    // PASS HEADERS COLLECTING
    const passHeaderY = passMaxTop - GEO.passHeaderMargin + GEO.headerMargin;
    let minHx = Infinity, maxHx = -Infinity;
    
    stagePermExits.forEach(p => {
      fullMarkup += streamPath([{ x: p.x, y: p.y }, { x: p.x, y: passHeaderY }], COLORS.permeate);
      minHx = Math.min(minHx, p.x);
      maxHx = Math.max(maxHx, p.x);
    });
    
    // Connect all permeate lines horizontally
    fullMarkup += streamPath([{ x: minHx, y: passHeaderY }, { x: maxHx, y: passHeaderY }], COLORS.permeate);

    passExits.push({
      permeateX: maxHx,
      permeateY: passHeaderY,
      concentrateX: lastConcExit.x,
      concentrateY: lastConcExit.y
    });

    sysMaxTop = Math.min(sysMaxTop, passHeaderY);
    sysMaxBottom = Math.max(sysMaxBottom, lastConcExit.y);

    // Coordinate prep for next pass
    x = stageX + GEO.passGap;

    // Double Pass connection: Pass 1 Permeate -> Pump -> Pass 2 Feed
    if (pi < state.passes.length - 1) {
      const p1ExitX = maxHx;
      const pumpCy = centerY + 13;
      const pumpCx = p1ExitX + 78;
      
      const newX = pumpCx + 90;
      const feedInXPass = newX - GEO.manifoldMargin;
      
      // Line into suction (center) - stops at left edge of motor housing
      fullMarkup += streamPath([
        { x: p1ExitX, y: passHeaderY },
        { x: p1ExitX + 18, y: passHeaderY },
        { x: p1ExitX + 18, y: pumpCy },
        { x: pumpCx - 46, y: pumpCy }
      ], COLORS.permeate, 'flow-fast', true);
      
      // Line out of discharge (top)
      fullMarkup += streamPath([
        { x: pumpCx, y: centerY },
        { x: feedInXPass, y: centerY }
      ], COLORS.permeate, 'flow-fast');
      
      // Add pump to pumps layer so it draws on top of the line
      pumpsMarkup += pumpIcon(pumpCx, pumpCy, 1, 'INTERPASS PUMP');
      
      x = newX; // Reposition starting x for Pass 2
    }
  });

  // FINAL OUTLETS: SYSTEM PERMEATE & CONCENTRATE
  const last = passExits[passExits.length - 1];
  
  // 1. Draw final permeate stream outlet with marker
  fullMarkup += streamPath([{ x: last.permeateX, y: last.permeateY }, { x: last.permeateX + GEO.outletStub, y: last.permeateY }], COLORS.permeate);
  // Arrow head marker
  fullMarkup += `<line x1="${last.permeateX + GEO.outletStub - 6}" y1="${last.permeateY}" x2="${last.permeateX + GEO.outletStub}" y2="${last.permeateY}" stroke="${COLORS.permeate}" stroke-width="2.6" marker-end="url(#pfd-ah-permeate)" />`;
  fullMarkup += `<text x="${last.permeateX + GEO.outletStub + 12}" y="${last.permeateY + 4}" font-size="13" font-weight="800" fill="${COLORS.permeate}" font-family="Outfit, sans-serif">PERMEATE</text>`;
  
  if (state.calc.showFlows) {
    const finalPerm = passExits.length > 1 ? passFlows[1].permeate : passFlows[0].permeate;
    fullMarkup += `<text x="${last.permeateX + 6}" y="${last.permeateY - 8}" font-size="10" font-weight="700" fill="${COLORS.permeate}" font-family="Fira Code, monospace">${finalPerm.toFixed(1)} m³/h</text>`;
  }

  // 2. Draw final concentrate collection manifold and outlet
  const finalManifoldY = Math.max(...passExits.map(p => p.concentrateY)) + 50; // drop down more to give space
  
  const hasPass2Recycle = state.passes.length >= 2;
  
  const elRecycleEnable = document.getElementById('calc-recycle-enable');
  const hasUserRecycle = elRecycleEnable && elRecycleEnable.checked;

  passExits.forEach((p, idx) => {
    // Drop down each pass concentrate to final bottom header
    fullMarkup += streamPath([
      { x: p.concentrateX, y: p.concentrateY },
      { x: p.concentrateX, y: finalManifoldY }
    ], COLORS.concentrate);
    
    // Add flow node labels for individual pass concentrate
    if (state.calc.showFlows) {
      fullMarkup += `<text x="${p.concentrateX + 4}" y="${(p.concentrateY + finalManifoldY) / 2}" font-size="8.5" font-weight="500" fill="${COLORS.concentrate}" font-family="Fira Code, monospace">${passFlows[idx].concentrate.toFixed(1)}</text>`;
    }
  });

  // Connect bottom header horizontally
  const firstConcX = passExits[0].concentrateX;
  const lastConcX = passExits[passExits.length - 1].concentrateX;
  if (passExits.length > 1) {
    fullMarkup += streamPath([{ x: firstConcX, y: finalManifoldY }, { x: lastConcX, y: finalManifoldY }], COLORS.concentrate);
  }
  
  // Final outlet
  fullMarkup += streamPath([{ x: lastConcX, y: finalManifoldY }, { x: lastConcX + GEO.outletStub, y: finalManifoldY }], COLORS.concentrate);
  
  // Base coordinates for any recycle loops
  const startMixCx = 60 - 10; 
  const startMixCy = centerY + 13;

  // Pass 2 inherent recycle (if 2-pass system)
  if (hasPass2Recycle) {
    const p = passExits[1];
    const branchY = p.concentrateY + 14; 
    const recycleDropX = p.concentrateX - 20; 
    const recycleY = finalManifoldY + 30;
    
    fullMarkup += streamPath([
      { x: p.concentrateX, y: branchY },
      { x: recycleDropX, y: branchY },
      { x: recycleDropX, y: recycleY },
      { x: startMixCx, y: recycleY },
      { x: startMixCx, y: startMixCy + 10 }
    ], COLORS.concentrate, 'flow-fast', true);
    
    if (state.calc.showFlows) {
      fullMarkup += `<text x="${startMixCx + 8}" y="${recycleY - 6}" font-size="8.5" font-weight="500" fill="${COLORS.concentrate}" font-family="Fira Code, monospace">Pass 2 Recycle</text>`;
    }
  }

  // User-configured Pass 1 Concentrate Recycle
  if (hasUserRecycle) {
    const p = passExits[0];
    const branchY = p.concentrateY + 28; 
    const recycleDropX = p.concentrateX - 40; 
    const recycleY = finalManifoldY + (hasPass2Recycle ? 50 : 30);
    
    fullMarkup += streamPath([
      { x: p.concentrateX, y: branchY },
      { x: recycleDropX, y: branchY },
      { x: recycleDropX, y: recycleY },
      { x: startMixCx - 10, y: recycleY },
      { x: startMixCx - 10, y: startMixCy + 10 }
    ], COLORS.concentrate, 'flow-fast', true);
    
    if (state.calc.showFlows) {
      const elRecycleRatio = document.getElementById('calc-recycle-ratio');
      const recRatio = elRecycleRatio ? elRecycleRatio.value : "0";
      fullMarkup += `<text x="${startMixCx - 2}" y="${recycleY - 6}" font-size="8.5" font-weight="500" fill="${COLORS.concentrate}" font-family="Fira Code, monospace">Pass 1 Recycle (${recRatio}%)</text>`;
    }
  }

  // Arrow head marker
  fullMarkup += `<line x1="${lastConcX + GEO.outletStub - 6}" y1="${finalManifoldY}" x2="${lastConcX + GEO.outletStub}" y2="${finalManifoldY}" stroke="${COLORS.concentrate}" stroke-width="2.6" marker-end="url(#pfd-ah-concentrate)" />`;
  fullMarkup += `<text x="${lastConcX + GEO.outletStub + 12}" y="${finalManifoldY + 4}" font-size="13" font-weight="800" fill="${COLORS.concentrate}" font-family="Outfit, sans-serif">CONCENTRATE</text>`;
  
  if (state.calc.showFlows) {
    const finalConc = Q_f - (passExits.length > 1 ? passFlows[1].permeate : passFlows[0].permeate);
    fullMarkup += `<text x="${lastConcX + 6}" y="${finalManifoldY + 16}" font-size="10" font-weight="700" fill="${COLORS.concentrate}" font-family="Fira Code, monospace">${finalConc.toFixed(1)} m³/h</text>`;
  }

  // Update bounds for viewBox sizing
  sysMaxBottom = Math.max(sysMaxBottom, finalManifoldY + (hasUserRecycle ? 70 : (hasPass2Recycle ? 50 : 30)));
  sysMaxTop = Math.min(sysMaxTop, last.permeateY - 40);

  const totalWidth = Math.max(last.permeateX, lastConcX) + GEO.outletStub + 150;
  const viewMinY = sysMaxTop - 30;
  const viewHeight = (sysMaxBottom + 30) - viewMinY;

  const svgOpening = `<svg id="pfdSvg" xmlns="http://www.w3.org/2000/svg" width="${totalWidth}" height="${viewHeight}" viewBox="0 ${viewMinY} ${totalWidth} ${viewHeight}" style="background-color: transparent;">`;
  
  return svgOpening + arrowMarkerDefs + fullMarkup + pumpsMarkup + `</svg>`;
}

    const svgContent = buildSVG();
    const containers = document.querySelectorAll('#pfd-svg-container');
    containers.forEach(c => {
        c.innerHTML = svgContent;
        c.style.background = 'var(--card-bg)';
        c.style.boxShadow = '0 2px 12px rgba(0,0,0,0.09)';
    });
};

// --- Make PFD Dynamic Based on User Inputs ---
window.updateLivePFD = function() {
    if (typeof window.drawPFDSVG === 'function') {
        const p1ArrText = document.getElementById('calc-vessels-array').value;
        const p1Arr = p1ArrText ? p1ArrText.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n) && n > 0) : [];
        const nEl = parseInt(document.getElementById('calc-elements-pv').value) || 6;
        const ro_results = window.lastCalcResult ? window.lastCalcResult.ro_results : null;
        
        window.drawPFDSVG(ro_results, p1Arr, nEl);
    }
};

// Add event listeners for live PFD updates when user changes stages/vessels/elements/flow
(function() {
    var elStages = document.getElementById('calc-stages');
    if (elStages) {
        elStages.addEventListener('input', function() { setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 50); });
        elStages.addEventListener('change', function() { setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 50); });
    }
    
    var elVessels = document.getElementById('calc-vessels-array');
    if (elVessels) {
        elVessels.addEventListener('input', function() { setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 50); });
        elVessels.addEventListener('change', function() { setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 50); });
    }
    
    var elElements = document.getElementById('calc-elements-pv');
    if (elElements) {
        elElements.addEventListener('input', function() { setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 50); });
        elElements.addEventListener('change', function() { setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 50); });
    }

    var elFlow = document.getElementById('flow');
    if (elFlow) {
        elFlow.addEventListener('input', function() { setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 50); });
        elFlow.addEventListener('change', function() { setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 50); });
    }

    // Event listeners for Concentrate Recycle input fields to update PFD dynamically
    var elRecycleEnable = document.getElementById('calc-recycle-enable');
    if (elRecycleEnable) {
        elRecycleEnable.addEventListener('change', function() { setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 50); });
    }

    var elRecycleRatio = document.getElementById('calc-recycle-ratio');
    if (elRecycleRatio) {
        elRecycleRatio.addEventListener('input', function() { setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 50); });
        elRecycleRatio.addEventListener('change', function() { setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 50); });
    }

    // Update cached membrane cost when user manually changes membrane selection
    var memSelect = document.getElementById('calc-ro-membrane');
    if (memSelect) {
        memSelect.addEventListener('change', function() {
            var ecoMemCost = document.getElementById('eco-mem-cost');
            if (ecoMemCost) {
                var selectedModel = memSelect.value;
                var price = 26880.0;
                if (selectedModel) {
                    var lower = selectedModel.toLowerCase();
                    if (lower.indexOf('nf') !== -1) {
                        price = 19200.0;
                    } else if (window.roMembranes && window.roMembranes[selectedModel]) {
                        var mem = window.roMembranes[selectedModel];
                        if ((mem.type && mem.type.toUpperCase() === 'SWRO') || 
                            (mem.nominal_rejection !== undefined && mem.nominal_rejection >= 0.995) || 
                            (mem.rejection_pct !== undefined && mem.rejection_pct >= 0.995)) {
                            price = 30240.0;
                        }
                    } else if (lower.indexOf('swro') !== -1 || lower.indexOf('sw30') !== -1 || lower.indexOf('hpa-ro') !== -1 || lower.indexOf('hparo') !== -1 || lower.indexOf('hpa-4040') !== -1) {
                        price = 30240.0;
                    }
                }
                ecoMemCost.value = price;
            }
        });
    }

    // Draw the PFD initially so it's not empty before the first run
    setTimeout(function() { if (typeof window.updateLivePFD === 'function') window.updateLivePFD(); }, 500);
})();

window.syncFeedToAging = function() {
    const sdiFeed = document.getElementById('sdi');
    const sdiAging = document.getElementById('aging-sdi');
    if (sdiFeed && sdiAging) sdiAging.value = sdiFeed.value;

    const tocFeed = document.getElementById('toc');
    const tocAging = document.getElementById('aging-toc');
    if (tocFeed && tocAging) tocAging.value = tocFeed.value;

    const tempFeed = document.getElementById('temp');
    const tempAging = document.getElementById('aging-temp');
    if (tempFeed && tempAging) tempAging.value = tempFeed.value;
};

document.addEventListener('DOMContentLoaded', () => {
    const sdiFeed = document.getElementById('sdi');
    const tocFeed = document.getElementById('toc');
    const tempFeed = document.getElementById('temp');
    if (sdiFeed) sdiFeed.addEventListener('input', window.syncFeedToAging);
    if (tocFeed) tocFeed.addEventListener('input', window.syncFeedToAging);
    if (tempFeed) tempFeed.addEventListener('input', window.syncFeedToAging);

    // Theme Toggle Logic
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    if (themeToggleBtn) {
        const savedTheme = localStorage.getItem('pace-theme') || 'light';
        if (savedTheme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            themeToggleBtn.innerHTML = '<i class="fa-solid fa-sun"></i>';
        }

        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            if (currentTheme === 'dark') {
                document.documentElement.removeAttribute('data-theme');
                localStorage.setItem('pace-theme', 'light');
                themeToggleBtn.innerHTML = '<i class="fa-solid fa-moon"></i>';
            } else {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('pace-theme', 'dark');
                themeToggleBtn.innerHTML = '<i class="fa-solid fa-sun"></i>';
            }

            // Redraw siChart with correct colors for light/dark theme
            if (window.siChart) {
                const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
                const tickColor = isDark ? '#94a3b8' : '#475569';
                const labelColor = isDark ? '#f8fafc' : '#1e293b';

                window.siChart.options.plugins.legend.labels.color = labelColor;
                window.siChart.options.scales.y.ticks.color = tickColor;
                window.siChart.options.scales.y.title.color = tickColor;
                window.siChart.options.scales.x.ticks.color = tickColor;
                window.siChart.update();
            }
        });
    }
});


/* ==========================================================================
   Membrane Physics Aging & Projection Event Handlers
   ========================================================================== */

window.togglePhysicsPanel = function() {
    const enabled = document.getElementById('calc-physics-enable').checked;
    const options = document.getElementById('calc-physics-options');
    if (options) {
        options.style.display = enabled ? 'block' : 'none';
    }
};

window.selectPhysicsYear = async function(year) {
    const hiddenInput = document.getElementById('phys-selected-year');
    if (hiddenInput) {
        hiddenInput.value = year;
    }
    
    // Highlight the button pill instantly in the UI for feedback
    const pills = document.querySelectorAll('.physics-year-pill');
    pills.forEach((p, idx) => {
        if (idx === year) {
            p.style.background = '#6366f1';
            p.style.color = 'white';
        } else {
            p.style.background = 'transparent';
            p.style.color = '#6366f1';
        }
    });

    // Trigger detailed calculation for the selected year
    const calcRunBtn = document.getElementById('calc-run-btn');
    if (calcRunBtn) {
        calcRunBtn.click();
    }
};

window.physNpfChartInstance = null;
window.physFoulingChartInstance = null;

window.renderPhysicsResults = function(data) {
    if (!data || !data.physics_results) return;
    
    const results = data.physics_results;
    window.lastPhysicsResult = results;   // store for antiscalant-aware SI risk thresholds
    const snapshots = results.annual_snapshots || [];
    const selectedYear = data.physics_selected_year || 0;
    
    // 1. Update pills classes
    const pills = document.querySelectorAll('.physics-year-pill');
    pills.forEach((p, idx) => {
        if (idx === selectedYear) {
            p.classList.add('active');
            p.style.background = '#6366f1';
            p.style.color = 'white';
        } else {
            p.classList.remove('active');
            p.style.background = 'transparent';
            p.style.color = '#6366f1';
        }
    });
    
    // 2. Update Banner and Header Label
    const bannerTitle = document.getElementById('phys-banner-title');
    if (bannerTitle) {
        bannerTitle.innerText = selectedYear === 0 ? "Year 0 – Baseline" : `Year ${selectedYear} – Projected`;
    }
    const cardYearLabel = document.getElementById('phys-card-year-label');
    if (cardYearLabel) {
        cardYearLabel.innerText = selectedYear === 0 ? "Year 0 (Baseline)" : `Year ${selectedYear}`;
    }
    
    // 3. Populate Comparison / Telemetry Cards
    const cur = snapshots.find(s => s.year === selectedYear) || snapshots[0];
    const base = snapshots[0];
    
    if (cur && base) {
        // Helper: safely set innerText only if element exists
        const setText = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };

        // Feed Pressure
        setText('phys-card-press', cur.feed_pressure_bar.toFixed(1));
        const pressDelta = document.getElementById('phys-card-press-delta');
        if (pressDelta) {
            if (selectedYear === 0) {
                pressDelta.innerText = "Baseline";
                pressDelta.style.color = "var(--text-secondary)";
            } else {
                const pct = ((cur.feed_pressure_bar - base.feed_pressure_bar) / base.feed_pressure_bar) * 100;
                pressDelta.innerText = `+${pct.toFixed(1)}% vs base`;
                pressDelta.style.color = "#f87171";
            }
        }

        // Permeate Flow
        setText('phys-card-flow', cur.perm_flow.toFixed(1));
        const flowDelta = document.getElementById('phys-card-flow-delta');
        if (flowDelta) {
            if (selectedYear === 0) {
                flowDelta.innerText = "Baseline";
                flowDelta.style.color = "var(--text-secondary)";
            } else {
                const pct = ((cur.perm_flow - base.perm_flow) / base.perm_flow) * 100;
                const sign = pct >= 0 ? '+' : '';
                flowDelta.innerText = `${sign}${pct.toFixed(1)}% vs base`;
                flowDelta.style.color = pct >= 0 ? "#34d399" : "#f87171";
            }
        }

        // NPF
        setText('phys-card-npf', cur.npf.toFixed(4));
        const npfDelta = document.getElementById('phys-card-npf-delta');
        if (npfDelta) {
            if (selectedYear === 0) {
                npfDelta.innerText = "Baseline";
                npfDelta.style.color = "var(--text-secondary)";
            } else {
                const pct = ((cur.npf - base.npf) / base.npf) * 100;
                const sign = pct >= 0 ? '+' : '';
                npfDelta.innerText = `${sign}${pct.toFixed(1)}% vs base`;
                npfDelta.style.color = pct >= 0 ? "#34d399" : "#f87171";
            }
        }

        // FRI, B_Rel, Recovery, TDS, SEC, CIPs
        setText('phys-card-fri',  cur.fri.toFixed(3));
        setText('phys-card-brel', cur.b_irr.toFixed(3));
        setText('phys-card-rec',  (cur.recovery * 100).toFixed(1));
        setText('phys-card-tds',  cur.perm_tds.toFixed(1));
        setText('phys-card-sec',  cur.sec_kwh_m3.toFixed(2));
        setText('phys-card-cips', cur.cip_count);
    }
    
    // 4. Render Table Body
    const tbody = document.getElementById('phys-annual-tbody');
    if (tbody) {
        tbody.innerHTML = snapshots.map(s => {
            const isSel = s.year === selectedYear;
            const style = isSel ? 'background: rgba(99, 102, 241, 0.08); font-weight: 600;' : '';
            return `
                <tr style="${style}">
                    <td><strong>Year ${s.year}</strong>${s.replacement_triggered ? ' <span title="Membranes were automatically replaced due to severe fouling (NPF < 0.70)" style="color: #ef4444; font-size: 0.65rem; background: rgba(239, 68, 68, 0.1); padding: 0.1rem 0.3rem; border-radius: 4px; margin-left: 0.3rem; border: 1px solid rgba(239, 68, 68, 0.2); cursor: help;">REPLACED</span>' : ''}</td>
                    <td>${s.perm_flow.toFixed(2)}</td>
                    <td>${(s.recovery * 100).toFixed(1)}%</td>
                    <td>${s.feed_pressure_bar.toFixed(1)}</td>
                    <td>${s.tmp_bar !== undefined ? s.tmp_bar.toFixed(1) : '-'}</td>
                    <td>${s.perm_tds.toFixed(1)}</td>
                    <td>${s.sec_kwh_m3.toFixed(2)}</td>
                    <td>${s.npf.toFixed(4)}</td>
                    <td>${s.nsp.toFixed(4)}</td>
                    <td>${s.fri.toFixed(3)}</td>
                    <td>${s.b_irr.toFixed(3)}</td>
                    <td>${s.ndp_ratio.toFixed(3)}</td>
                </tr>
            `;
        }).join('');
    }
    
    // 5. Render Charts
    window.renderPhysicsCharts(snapshots);

    // 6. Update Fouling Breakdown
    const foulTbody = document.getElementById('phys-fouling-tbody');
    const foulingLabel = document.getElementById('phys-fouling-year-label');
    if (foulingLabel) foulingLabel.innerText = `Year ${selectedYear}`;
    if (foulTbody && cur && base) {
        const totalR = (cur.rc_avg || 0) + (cur.rb_avg || 0) + (cur.rs_avg || 0) + (cur.rn_avg || 0);
        const mechanisms = [
            { name: "Particulate/Cake (Rc)", val: cur.rc_avg || 0, isFoul: true },
            { name: "Biofouling (Rb)", val: cur.rb_avg || 0, isFoul: true },
            { name: "Scaling (Rs)", val: cur.rs_avg || 0, isFoul: true },
            { name: "Organic/NOM (Rn)", val: cur.rn_avg || 0, isFoul: true },
            { name: "Compaction (Structural)", val: cur.rcomp || 0, isFoul: false }
        ];
        foulTbody.innerHTML = mechanisms.map(m => {
            const pct = (m.isFoul && totalR > 0) ? (m.val / totalR) * 100 : null;
            const status = m.isFoul ? (pct > 40 ? '<span style="color:#ef4444;font-weight:bold;">Critical</span>' : (pct > 20 ? '<span style="color:#f59e0b;font-weight:bold;">Elevated</span>' : '<span style="color:#10b981;">Normal</span>')) : '<span style="color:#64748b;">N/A</span>';
            const pctStr = pct !== null ? pct.toFixed(1) + '%' : 'N/A';
            return `<tr><td>${m.name}</td><td>${m.val.toExponential(2)}</td><td>${pctStr}</td><td>${status}</td></tr>`;
        }).join('');
    }

    // 7. Update SI Comparison
    const siTbody = document.getElementById('phys-si-tbody');
    const siLabel = document.getElementById('phys-si-year-label');
    if (siLabel) siLabel.innerText = `Year ${selectedYear}`;
    if (siTbody && cur && base) {
        // Antiscalant-aware industry-standard SI limits (Filmtec/Hydranautics design guidelines)
        // limit     = threshold without antiscalant  (strict, thermodynamic precipitation onset)
        // limitAS   = threshold with antiscalant     (vendor-approved operating envelope)
        // caution   = low-risk buffer below limit     (early warning zone)
        const antiscalantOn = (window.lastPhysicsResult && window.lastPhysicsResult.antiscalant_dosed) ? true : false;
        const minerals = [
            { name: "Calcite (CaCO₃)", bulk: cur.si_calcite_bulk, yr0: base.si_calcite_wall || 0, cur: cur.si_calcite_wall || 0,
              limit: 0.0, limitAS: 0.5, caution: -0.2,
              note: "LSI threshold: 0.0 (no AS), +0.5 (with antiscalant)" },
            { name: "Gypsum (CaSO₄)", bulk: cur.si_gypsum_bulk, yr0: base.si_gypsum_wall || 0, cur: cur.si_gypsum_wall || 0,
              limit: 0.0, limitAS: 0.0, caution: -0.2,
              note: "Threshold: SI = 0.0 (antiscalant provides kinetic delay only)" },
            { name: "Barite (BaSO₄)", bulk: cur.si_barite_bulk, yr0: base.si_barite_wall || 0, cur: cur.si_barite_wall || 0,
              limit: -0.3, limitAS: 0.0, caution: -0.5,
              note: "Barite is irreversible — conservative limit below 0.0" },
            { name: "Amorphous Silica", bulk: cur.si_silica_bulk, yr0: base.si_silica_wall || 0, cur: cur.si_silica_wall || 0,
              limit: 0.0, limitAS: 0.2, caution: -0.1,
              note: "Silica threshold: 0.0 (no AS), +0.2 (with antiscalant)" }
        ];
        siTbody.innerHTML = minerals.map(m => {
            const activeLimit   = antiscalantOn ? m.limitAS : m.limit;
            const cautionLimit  = antiscalantOn ? m.caution + (m.limitAS - m.limit) : m.caution;
            let status;
            if (m.cur >= activeLimit) {
                status = '<span style="color:#ef4444;font-weight:bold;">⚠ High Risk</span>';
            } else if (m.cur >= cautionLimit) {
                status = '<span style="color:#f59e0b;font-weight:bold;">⚡ Caution</span>';
            } else {
                status = '<span style="color:#10b981;">✓ Low Risk</span>';
            }
            const bulkVal = typeof m.bulk === 'number' ? m.bulk.toFixed(2) : '--';
            const limitStr = antiscalantOn ? `${m.limitAS.toFixed(1)} (AS)` : `${m.limit.toFixed(1)}`;
            return `<tr title="${m.note}"><td>${m.name}</td><td>${bulkVal}</td><td>${m.yr0.toFixed(2)}</td><td><strong>${m.cur.toFixed(2)}</strong></td><td>${limitStr}</td><td>${status}</td></tr>`;
        }).join('');
    }
};

window.renderPhysicsCharts = function(snapshots) {
    const chartSnaps = [];
    snapshots.forEach((s, i) => {
        chartSnaps.push({ label: s.year === 0 ? 'Baseline' : `Year ${s.year}`, snap: s });
        // If a replacement happened this year, explicitly inject the clean baseline 
        // immediately after the fouled state so the chart visually drops back down.
        if (s.replacement_triggered && i > 0) {
            chartSnaps.push({
                label: `Yr ${s.year} (New)`,
                snap: { ...snapshots[0], year: s.year } 
            });
        }
    });

    const labels = chartSnaps.map(cs => cs.label);
    const npfData = chartSnaps.map(cs => cs.snap.npf);
    const nspData = chartSnaps.map(cs => cs.snap.nsp);
    
    // 1. NPF & NSP Chart
    const ctxNpf = document.getElementById('phys-npf-chart');
    if (ctxNpf) {
        if (window.physNpfChartInstance) window.physNpfChartInstance.destroy();
        window.physNpfChartInstance = new Chart(ctxNpf, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'NPF (Normalized Flow)',
                        data: npfData,
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99, 102, 241, 0.05)',
                        borderWidth: 2,
                        tension: 0.25,
                        fill: true
                    },
                    {
                        label: 'NSP (Normalized Salt Passage)',
                        data: nspData,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.05)',
                        borderWidth: 2,
                        tension: 0.25,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: false,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: {
                            color: '#94a3b8',
                            // Show 4 decimal places so small NPF/NSP changes are visible
                            callback: (v) => v.toFixed(4)
                        }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#94a3b8' }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#e2e8f0', font: { size: 10 } }
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(4)}`
                        }
                    }
                }
            }
        });
    }
    
    // 2. Fouling Mechanism Chart
    const ctxFouling = document.getElementById('phys-fouling-chart');
    if (ctxFouling) {
        const rcData = chartSnaps.map(cs => cs.snap.rc_avg || 0);
        const rbData = chartSnaps.map(cs => cs.snap.rb_avg || 0);
        const rnData = chartSnaps.map(cs => cs.snap.rn_avg || 0);
        const rsData = chartSnaps.map(cs => cs.snap.rs_avg || 0);
        
        if (window.physFoulingChartInstance) window.physFoulingChartInstance.destroy();
        window.physFoulingChartInstance = new Chart(ctxFouling, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Cake Filtration',
                        data: rcData,
                        backgroundColor: '#ef4444'
                    },
                    {
                        label: 'Biofouling',
                        data: rbData,
                        backgroundColor: '#10b981'
                    },
                    {
                        label: 'NOM Adsorption',
                        data: rnData,
                        backgroundColor: '#3b82f6'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        stacked: true,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    },
                    x: {
                        stacked: true,
                        grid: { display: false },
                        ticks: { color: '#94a3b8' }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#e2e8f0', font: { size: 10 } }
                    }
                }
            }
        });
    }

    // 3. Feed Pressure & SEC Trend Chart
    const ctxPressure = document.getElementById('phys-pressure-chart');
    if (ctxPressure) {
        const pressureData = chartSnaps.map(cs => cs.snap.feed_pressure_bar || 0);
        const secData = chartSnaps.map(cs => cs.snap.sec_kwh_m3 || 0);
        
        if (window.physPressureChartInstance) window.physPressureChartInstance.destroy();
        window.physPressureChartInstance = new Chart(ctxPressure, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Feed Pressure (bar)',
                        data: pressureData,
                        borderColor: '#fbbf24',
                        backgroundColor: 'rgba(251, 191, 36, 0.05)',
                        borderWidth: 2,
                        tension: 0.25,
                        yAxisID: 'y'
                    },
                    {
                        label: 'SEC (kWh/m³)',
                        data: secData,
                        borderColor: '#a855f7',
                        backgroundColor: 'rgba(168, 85, 247, 0.05)',
                        borderWidth: 2,
                        tension: 0.25,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { display: false },
                        ticks: { color: '#94a3b8' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#94a3b8' }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#e2e8f0', font: { size: 10 } }
                    }
                }
            }
        });
    }
};

// --- Membrane Directory Modal Logic ---
window.membraneDbCache = { ro: [], nf: [], uf: [] };
window.activeMembraneTab = 'RO';

window.handleMembraneDbClick = function(e) {
    const btn = document.getElementById('membrane-db-btn');
    if (btn && btn.classList.contains('pace-locked-tab')) {
        const toast = document.getElementById('pace-lock-toast');
        if (toast) {
            toast.style.display = 'flex';
            setTimeout(() => { toast.style.display = 'none'; }, 3000);
        }
        return;
    }
    window.openMembraneDbModal();
};

window.openMembraneDbModal = async function() {
    const btn = document.getElementById('membrane-db-btn');
    if (btn) btn.classList.add('active');

    const modal = document.getElementById('membrane-db-modal');
    if (modal) modal.classList.add('is-active');
    
    const tbody = document.getElementById('pace-db-tbody');
    const countEl = document.getElementById('pace-db-count');
    
    // Clear and show loading
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 2rem; color: var(--text-secondary);"><i class="fa-solid fa-spinner fa-spin"></i> Fetching membrane database...</td></tr>`;
    if (countEl) countEl.innerText = "Loading membranes...";

    try {
        const response = await fetch(API_BASE + '/api/membranes');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        const roMems = data.ro_membranes || [];
        const ufMems = data.uf_modules || [];
        
        // Segregate into cache
        // RO: Only show Permionics' membranes
        window.membraneDbCache.ro = roMems.filter(m => {
            const type = (m.type || '').toUpperCase();
            const isRO = type === 'BWRO' || type === 'SWRO' || type === 'RO';
            const isPerm = m.manufacturer && m.manufacturer.toLowerCase() === 'permionics';
            return isRO && isPerm;
        });

        // NF: Show all NF membranes available in the database (no manufacturer filter)
        window.membraneDbCache.nf = roMems.filter(m => {
            const type = (m.type || '').toUpperCase();
            return type === 'NF';
        });

        // UF: Show all UF modules available in the database (no manufacturer filter)
        window.membraneDbCache.uf = ufMems.map(m => {
            return {
                id: m.id,
                name: m.name,
                type: 'UF',
                manufacturer: m.manufacturer || 'FilmTec',
                area: m.area,
                feed_spacer_mil: null,
                nominal_rejection: null,
                max_pressure_bar: 3.0,
                max_feed_flow_m3h: null,
                max_recovery_pct: 95.0,
                length_m: null,
                diameter_m: null,
                material: 'PVDF'
            };
        });

        // Default to RO tab
        window.switchMembraneTypeTab('RO');

    } catch (err) {
        console.warn("API database fetch failed, falling back to local membrane database cache:", err);
        try {
            const localMems = Object.entries(window.roMembranes || {}).map(([k, v]) => {
                return {
                    id: k,
                    name: k,
                    type: v.type,
                    manufacturer: v.manufacturer,
                    area: v.active_area_m2,
                    feed_spacer_mil: v.feed_spacer_mil,
                    nominal_rejection: v.nominal_rejection,
                    max_pressure_bar: v.max_pressure_bar,
                    max_feed_flow_m3h: v.max_feed_flow_m3h,
                    min_conc_flow_m3h: v.min_conc_flow_m3h,
                    max_recovery_pct: v.max_recovery_pct,
                    length_m: v.length_m,
                    diameter_m: v.diameter_m,
                    material: v.material || 'Polyamide Composite'
                };
            });
            
            // RO: Only show Permionics' membranes
            window.membraneDbCache.ro = localMems.filter(m => {
                const type = (m.type || '').toUpperCase();
                const isRO = type === 'BWRO' || type === 'SWRO' || type === 'RO';
                const isPerm = m.manufacturer && m.manufacturer.toLowerCase() === 'permionics';
                return isRO && isPerm;
            });

            // NF: Show all NF membranes available in the database
            window.membraneDbCache.nf = localMems.filter(m => {
                const type = (m.type || '').toUpperCase();
                return type === 'NF';
            });

            // UF fallback
            window.membraneDbCache.uf = [
                { id: "SFP-2860", name: "SFP-2860", type: "UF", manufacturer: "FilmTec", area: 51.0, feed_spacer_mil: null, nominal_rejection: null, max_pressure_bar: 3.0, max_feed_flow_m3h: null, max_recovery_pct: 95.0, length_m: null, diameter_m: null, material: "PVDF" },
                { id: "SFP-2880", name: "SFP-2880", type: "UF", manufacturer: "FilmTec", area: 77.0, feed_spacer_mil: null, nominal_rejection: null, max_pressure_bar: 3.0, max_feed_flow_m3h: null, max_recovery_pct: 95.0, length_m: null, diameter_m: null, material: "PVDF" }
            ];

            window.switchMembraneTypeTab('RO');
        } catch (fallbackErr) {
            console.error("Local fallback failed:", fallbackErr);
            if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 2rem; color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Error loading database: ${err.message}</td></tr>`;
            if (countEl) countEl.innerText = "Failed to load.";
        }
    }
};

window.closeMembraneDbModal = function() {
    const btn = document.getElementById('membrane-db-btn');
    if (btn) btn.classList.remove('active');

    const modal = document.getElementById('membrane-db-modal');
    if (modal) modal.classList.remove('is-active');
};

window.switchMembraneTypeTab = function(tabName) {
    window.activeMembraneTab = tabName;
    
    // Update active state of pills
    document.querySelectorAll('.membrane-tabs .tab-pill').forEach(btn => {
        btn.classList.remove('active');
        btn.style.border = '1px solid transparent';
        btn.style.background = 'transparent';
        btn.style.color = 'var(--text-secondary)';
    });
    
    const activeBtn = document.getElementById(`mem-tab-${tabName.toLowerCase()}`);
    if (activeBtn) {
        activeBtn.classList.add('active');
        activeBtn.style.border = '1px solid var(--accent-color)';
        activeBtn.style.background = 'rgba(59, 130, 246, 0.1)';
        activeBtn.style.color = 'var(--text-primary)';
    }

    // Refresh display
    window.filterMembraneDbTable();
};

window.renderMembraneDbTable = function(membranes) {
    const tbody = document.getElementById('pace-db-tbody');
    const countEl = document.getElementById('pace-db-count');
    
    if (countEl) countEl.innerText = `${membranes.length} membranes found`;
    if (!tbody) return;

    if (membranes.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 2rem; color: var(--text-secondary);">No matching membranes found.</td></tr>`;
        return;
    }

    tbody.innerHTML = membranes.map(m => {
        let typeBadge = '';
        if (m.type === 'SWRO') typeBadge = `<span class="pace-badge pace-badge-sw">SWRO</span>`;
        else if (m.type === 'BWRO') typeBadge = `<span class="pace-badge pace-badge-bw">BWRO</span>`;
        else if (m.type === 'NF') typeBadge = `<span class="pace-badge" style="background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4);">NF</span>`;
        else if (m.type === 'UF') typeBadge = `<span class="pace-badge" style="background: rgba(234, 179, 8, 0.2); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.4);">UF</span>`;
        else typeBadge = `<span class="pace-badge pace-badge-bw">${m.type || 'RO'}</span>`;
        
        const mat = m.material || 'Polyamide Composite';
        const area = m.area ? `${m.area.toFixed(1)} m²` : '--';
        const spacer = m.feed_spacer_mil ? `${m.feed_spacer_mil} mil` : '--';
        const rej = m.nominal_rejection ? `${(m.nominal_rejection * 100).toFixed(2)}%` : '--';
        const press = m.max_pressure_bar ? `${m.max_pressure_bar.toFixed(1)} bar` : '--';
        const maxFlow = m.max_feed_flow_m3h ? `${m.max_feed_flow_m3h.toFixed(2)} m³/h` : '--';
        const maxRec = m.max_recovery_pct ? `${m.max_recovery_pct.toFixed(0)}%` : '--';

        return `
            <tr>
                <td style="font-weight: 700;">${m.id}</td>
                <td>${typeBadge}</td>
                <td style="font-weight: 500; color: var(--text-secondary);">${mat}</td>
                <td>${area}</td>
                <td>${spacer}</td>
                <td><strong>${rej}</strong></td>
                <td>${press}</td>
                <td>${maxFlow}</td>
                <td>${maxRec}</td>
            </tr>
        `;
    }).join('');
};

window.filterMembraneDbTable = function() {
    const q = document.getElementById('pace-db-search').value.toLowerCase().trim();
    const activeTab = window.activeMembraneTab || 'RO';
    
    let list = [];
    if (activeTab === 'RO') list = window.membraneDbCache.ro;
    else if (activeTab === 'NF') list = window.membraneDbCache.nf;
    else if (activeTab === 'UF') list = window.membraneDbCache.uf;

    if (q) {
        list = list.filter(m => {
            return (
                m.id.toLowerCase().includes(q) ||
                (m.type && m.type.toLowerCase().includes(q)) ||
                (m.material && m.material.toLowerCase().includes(q)) ||
                (m.area && m.area.toString().includes(q))
            );
        });
    }
    window.renderMembraneDbTable(list);
};

window.openUserInfoModal = function(event) {
    if (event) event.preventDefault();
    const modal = document.getElementById('user-info-modal');
    if (modal) modal.classList.add('is-active');
};

window.closeUserInfoModal = function() {
    const modal = document.getElementById('user-info-modal');
    if (modal) modal.classList.remove('is-active');
};

window.saveUserInfoModal = function() {
    const data = {
        firstName: document.getElementById('user-first-name').value.trim(),
        lastName: document.getElementById('user-last-name').value.trim(),
        company: document.getElementById('user-company').value.trim(),
        email: document.getElementById('user-email').value.trim(),
        office: document.getElementById('user-office').value.trim(),
        mobile: document.getElementById('user-mobile').value.trim(),
        fax: document.getElementById('user-fax').value.trim(),
        street: document.getElementById('user-street').value.trim(),
        city: document.getElementById('user-city').value.trim(),
        country: document.getElementById('user-country').value.trim(),
        uiLang: document.getElementById('user-ui-lang').value,
        reportLang: document.getElementById('user-report-lang').value
    };
    
    localStorage.setItem('pace_user_info', JSON.stringify(data));
    
    // Update initials in profile icon
    let initials = '';
    if (data.firstName) initials += data.firstName[0];
    if (data.lastName) initials += data.lastName[0];
    initials = initials.toUpperCase() || 'JD';
    
    const profileBtn = document.querySelector('.user-profile');
    if (profileBtn) profileBtn.textContent = initials;
    
    window.closeUserInfoModal();
};


/* ==========================================================================
   Membrane Aging Simulation (Time-series / Single Pass)
   ========================================================================== */

window.getFeedWaterData = function() {
    const safeVal = (id) => {
        const el = document.getElementById(id);
        if (!el) return 0;
        return parseFloat(el.value || el.textContent) || 0;
    };

    return {
        calcium: safeVal('ca'),
        magnesium: safeVal('mg'),
        sodium: safeVal('na'),
        potassium: safeVal('k'),
        ammonium: safeVal('nh4'),
        barium: safeVal('ba'),
        strontium: safeVal('sr'),
        chloride: safeVal('cl'),
        sulfate: safeVal('so4'),
        bicarbonate: safeVal('hco3'),
        carbonate: safeVal('co3'),
        nitrate: safeVal('no3'),
        fluoride: safeVal('f'),
        phosphate: safeVal('po4'),
        silica: safeVal('sio2'),
        ph: safeVal('ph') || 7.0,
        temperature: safeVal('temp') || 25.0,
        tds: parseFloat(document.getElementById('calc-tds')?.textContent) || 0.0,
        tss: safeVal('tss'),
        turbidity: safeVal('turbidity')
    };
};

window.runAgingSimulation = async function() {
    const btn = document.getElementById('aging-run-btn');
    if (!btn) return;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Simulating Aging...';
    btn.disabled = true;

    try {
        const feedWater = window.getFeedWaterData();
        const flow = parseFloat(document.getElementById('flow').value) || 10.0;
        const recovery = parseFloat(document.getElementById('recovery').value) || 75.0;

        const payload = {
            technology_train: document.getElementById('calc-tech-train') ? document.getElementById('calc-tech-train').value : 'RO',
            feed_water: feedWater,
            system_config: {
                membrane: document.getElementById('ro-membrane') ? document.getElementById('ro-membrane').value : 'BW30-400',
                stages: parseInt(document.getElementById('stages') ? document.getElementById('stages').value : 1),
                vessels_per_stage: (document.getElementById('vessels-stage-1') ? [parseInt(document.getElementById('vessels-stage-1').value), parseInt(document.getElementById('vessels-stage-2') ? document.getElementById('vessels-stage-2').value : 0)].filter(v => v>0) : [1]),
                elements_per_vessel: parseInt(document.getElementById('elements-per-vessel') ? document.getElementById('elements-per-vessel').value : 6),
                target_recovery_pct: recovery
            },
            aging_config: {
                design_life_months: parseInt(document.getElementById('aging-design-life').value) || 60,
                time_step_months: 1,
                simulation_mode: document.getElementById('aging-sim-mode').value || 'constant_recovery',
                cip_trigger: document.getElementById('aging-cip-mode').value || 'scheduled',
                cip_interval_days: parseInt(document.getElementById('aging-cip-interval').value) || 90,
                cip_type: 'acid_alkaline_sequential',
                antiscalant_dosed: document.getElementById('aging-antiscalant').checked
            },
            feed_history: {
                sdi15: parseFloat(document.getElementById('aging-sdi').value) || 3.0,
                toc_mg_l: parseFloat(document.getElementById('aging-toc').value) || 2.0,
                temperature_c: parseFloat(document.getElementById('aging-temp').value) || 28.0,
                cl2_residual_mg_l: parseFloat(document.getElementById('aging-cl2').value) || 0.0
            },
            target_flow_m3h: flow
        };

        const response = await fetch(API_BASE + '/api/simulate-aging', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Simulation failed');
        }

        const result = await response.json();
        window.renderAgingResults(result, payload.aging_config.design_life_months);

    } catch (error) {
        console.error(error);
        alert('Aging simulation failed: ' + error.message);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
};

window.renderAgingResults = function(data, designLifeMonths) {
    // Reveal Cards
    document.getElementById('aging-eol-card').style.display = 'block';
    document.getElementById('aging-autopsy-card').style.display = 'block';
    document.getElementById('aging-highlights-card').style.display = 'block';
    document.getElementById('aging-chart-card').style.display = 'block';
    document.getElementById('aging-mechanism-card').style.display = 'block';
    document.getElementById('aging-table-card').style.display = 'block';

    const profile = data.aging_profile || [];
    const finalMonthState = profile[profile.length - 1] || {};

    // Highlights
    document.getElementById('aging-hl-npf').textContent = finalMonthState.npf ? finalMonthState.npf.toFixed(2) : '1.00';
    document.getElementById('aging-hl-pfeed').textContent = finalMonthState.p_feed_bar ? finalMonthState.p_feed_bar.toFixed(1) : '--';
    document.getElementById('aging-hl-cips').textContent = data.cip_events ? data.cip_events.length : 0;
    
    const eolReached = data.end_of_life_month !== null;
    const eolMonthStr = eolReached ? data.end_of_life_month : `> ${designLifeMonths}`;
    document.getElementById('aging-eol-month').textContent = eolMonthStr;
    document.getElementById('aging-hl-eol').textContent = eolMonthStr;
    document.getElementById('aging-dominant-mech').textContent = (data.dominant_mechanism || 'N/A').replace('_', ' ').toUpperCase();

    // Monthly Profile Table
    const tbody = document.getElementById('aging-monthly-tbody');
    if (tbody) {
        tbody.innerHTML = '';
        profile.forEach(pt => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>Month ${pt.month}</td>
                <td style="color: var(--accent-color); font-weight: 600;">${pt.p_feed_bar.toFixed(2)}</td>
                <td>${pt.npf.toFixed(2)}</td>
                <td>${(pt.nsr * 100).toFixed(1)}%</td>
                <td>${pt.delta_p_ratio.toFixed(2)}</td>
                <td>${pt.flux_lmh.toFixed(1)}</td>
                <td>${pt.recovery_pct.toFixed(1)}%</td>
                <td>${pt.cip_event ? '✅' : ''}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    // Autopsy Table
    const autoTbody = document.getElementById('aging-autopsy-tbody');
    if (autoTbody && data.element_autopsy) {
        autoTbody.innerHTML = '';
        const sortedKeys = Object.keys(data.element_autopsy).sort((a, b) => {
            const m1 = a.match(/s(\d+)_e(\d+)/);
            const m2 = b.match(/s(\d+)_e(\d+)/);
            if (m1 && m2) {
                const s1 = parseInt(m1[1]), e1 = parseInt(m1[2]);
                const s2 = parseInt(m2[1]), e2 = parseInt(m2[2]);
                return s1 !== s2 ? s1 - s2 : e1 - e2;
            }
            return 0;
        });

        sortedKeys.forEach(key => {
            const el = data.element_autopsy[key];
            const m = key.match(/s(\d+)_e(\d+)/);
            const nameStr = m ? `Stage ${m[1]} - Element ${m[2]}` : key;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${nameStr}</strong></td>
                <td>${el.fri_cake.toFixed(3)}</td>
                <td>${el.fri_bio.toFixed(3)}</td>
                <td>${el.fri_nom.toFixed(3)}</td>
                <td>${el.fri_scale.toFixed(3)}</td>
                <td style="font-weight: bold;">${el.fri_total.toFixed(3)}</td>
                <td>${(el.a_eff * 100).toFixed(1)}%</td>
            `;
            autoTbody.appendChild(tr);
        });
    }

    // Mechanism Breakdown Chart (Doughnut)
    window.drawMechanismChart(data.mechanism_totals || {});

    // Performance Chart (Line Chart)
    window.drawPerformanceChart(profile);
};

window.agingChartInstance = null;
window.mechanismChartInstance = null;

window.drawPerformanceChart = function(profile) {
    const ctxEl = document.getElementById('aging-canvas-npf');
    if (!ctxEl) return;
    const ctx = ctxEl.getContext('2d');
    
    if (window.agingChartInstance) {
        window.agingChartInstance.destroy();
    }

    const labels = profile.map(s => `Month ${s.month}`);
    const npfData = profile.map(s => s.npf);
    const pressData = profile.map(s => s.p_feed_bar);
    const cipPoints = profile.map(s => s.cip_event ? s.npf : null);

    window.agingChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'NPF (Normalized Flow Ratio)',
                    data: npfData,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.05)',
                    yAxisID: 'y',
                    fill: true,
                    tension: 0.1
                },
                {
                    label: 'Feed Pressure (bar)',
                    data: pressData,
                    borderColor: '#ef4444',
                    borderDash: [5, 5],
                    yAxisID: 'y1',
                    fill: false,
                    tension: 0.1
                },
                {
                    label: 'CIP Events',
                    data: cipPoints,
                    type: 'scatter',
                    backgroundColor: '#fb923c',
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    yAxisID: 'y'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    title: { display: true, text: 'NPF Ratio', color: '#94a3b8' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    ticks: { color: '#94a3b8' },
                    title: { display: true, text: 'Pressure (bar)', color: '#94a3b8' },
                    grid: { drawOnChartArea: false }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#e2e8f0', font: { size: 10 } }
                }
            }
        }
    });
};

window.drawMechanismChart = function(totals) {
    const ctxEl = document.getElementById('aging-canvas-mechanism');
    if (!ctxEl) return;
    const ctx = ctxEl.getContext('2d');
    
    if (window.mechanismChartInstance) {
        window.mechanismChartInstance.destroy();
    }

    const data = [
        totals.cake || 0,
        totals.bio || 0,
        totals.nom || 0,
        totals.scale || 0,
        totals.irreversible || 0
    ];

    window.mechanismChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Particulate', 'Biofouling', 'Organic', 'Scaling', 'Irreversible (Comp/Oxid)'],
            datasets: [{
                data: data,
                backgroundColor: [
                    '#f59e0b', // amber
                    '#10b981', // emerald
                    '#8b5cf6', // violet
                    '#3b82f6', // blue
                    '#ef4444'  // red
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { boxWidth: 12, font: { size: 10 }, color: '#e2e8f0' }
                }
            }
        }
    });
};

window.exportWaterAnalysis = async function() {
    const data = {};
    const generalFields = ['ph', 'temperature', 'tds', 'tss', 'toc', 'sdi'];
    generalFields.forEach(id => {
        const el = document.getElementById(id);
        if (el) data[id] = el.value;
    });

    document.querySelectorAll('.ion-input').forEach(input => {
        if (input.id) data[input.id] = input.value;
    });

    const jsonStr = JSON.stringify(data, null, 2);

    try {
        if ('showSaveFilePicker' in window) {
            const handle = await window.showSaveFilePicker({
                suggestedName: 'water_analysis.json',
                types: [{
                    description: 'JSON Files',
                    accept: {'application/json': ['.json']},
                }],
            });
            const writable = await handle.createWritable();
            await writable.write(jsonStr);
            await writable.close();
        } else {
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(jsonStr);
            const downloadAnchorNode = document.createElement('a');
            downloadAnchorNode.setAttribute("href", dataStr);
            downloadAnchorNode.setAttribute("download", "water_analysis.json");
            document.body.appendChild(downloadAnchorNode); 
            downloadAnchorNode.click();
            downloadAnchorNode.remove();
        }
    } catch (err) {
        if (err.name !== 'AbortError') {
            console.error("Error saving file:", err);
        }
    }
};

window.importWaterAnalysis = function() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.json';
    fileInput.onchange = e => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = e => {
            try {
                const data = JSON.parse(e.target.result);
                Object.keys(data).forEach(key => {
                    const el = document.getElementById(key);
                    if (el) {
                        el.value = data[key];
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                });
                if (typeof calculateChemistry === 'function') {
                    calculateChemistry(true);
                }
            } catch (err) {
                alert("Invalid JSON file");
            }
        };
        reader.readAsText(file);
    };
    fileInput.click();
};
