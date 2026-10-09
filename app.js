(function () {
    'use strict';

    var feedBlocks = [];
    var typingTimer = null;
    var isDesktop = window.innerWidth > 768;
    var curSession = Date.now();
    var sessions = [];

    try {
        sessions = JSON.parse(sessionStorage.getItem('kara_sessions') || '[]');
        if (!Array.isArray(sessions)) sessions = [];
    } catch (e) {
        sessions = [];
    }

    var ambientGlow = document.getElementById('ambientGlow');
    var mainInput = document.getElementById('mainInput');
    var mirrorText = document.getElementById('mirrorText');
    var hintText = document.getElementById('hintText');
    var brandBtn = document.getElementById('brandBtn');

    var viewLanding = document.getElementById('viewLanding');
    var viewResults = document.getElementById('viewResults');
    var feedContainer = document.getElementById('feedContainer');
    var followupInput = document.getElementById('followupInput');

    var historyTrack = document.getElementById('historyTrack');
    var menuBtn = document.getElementById('menuBtn');
    var closeSidebarBtn = document.getElementById('closeSidebarBtn');
    var sidebarPanel = document.getElementById('sidebarPanel');
    var sidebarList = document.getElementById('sidebarList');

    function cleanOldSourceBadges(root) {
        var badges = (root || document).querySelectorAll('.source-layer');
        for (var i = 0; i < badges.length; i++) badges[i].remove();
    }

    function escapeHtml(str) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(str));
        return d.innerHTML;
    }

    if (isDesktop) {
        window.addEventListener('mousemove', function (e) {
            var gx = (e.clientX / window.innerWidth - 0.5) * 20;
            var gy = (e.clientY / window.innerHeight - 0.5) * 20;
            if (ambientGlow) {
                ambientGlow.style.transform = 'translate(calc(-50% + ' + gx + '%), calc(-50% + ' + gy + '%))';
            }
        });

        window.attachHover = function () {
            var items = document.querySelectorAll('a, button, .hist-dot, .source-item, .sidebar-item');
            for (var i = 0; i < items.length; i++) {
                var el = items[i];
                if (!el.dataset.hasHover) {
                    el.addEventListener('mouseenter', function () { document.body.classList.add('hovering'); });
                    el.addEventListener('mouseleave', function () { document.body.classList.remove('hovering'); });
                    el.dataset.hasHover = 'true';
                }
            }
        };
        window.attachHover();
    }

    function saveSession() {
        if (feedBlocks.length === 0) return;

        sessions = sessions.filter(function (s) { return s.id !== curSession; });

        sessions.unshift({
            id: curSession,
            title: feedBlocks[0].query,
            blocks: feedBlocks.slice(),
            timestamp: Date.now()
        });

        if (sessions.length > 15) sessions.pop();

        try {
            sessionStorage.setItem('kara_sessions', JSON.stringify(sessions));
        } catch (e) {
        }
        renderSidebar();
    }

    function renderSidebar() {
        if (sessions.length === 0) {
            sidebarList.innerHTML = '<div style="opacity:0.5; font-size: 0.8rem; padding: 20px 0;">No past conversations.</div>';
            return;
        }

        var html = '';
        for (var i = 0; i < sessions.length; i++) {
            html += '<div class="sidebar-item" data-session="' + sessions[i].id + '">' + escapeHtml(sessions[i].title) + '</div>';
        }
        sidebarList.innerHTML = html;

        var items = document.querySelectorAll('.sidebar-item');
        for (var j = 0; j < items.length; j++) {
            items[j].addEventListener('click', function () {
                var sid = parseInt(this.getAttribute('data-session'));
                restoreSession(sid);
                sidebarPanel.classList.remove('open');
            });
        }

        if (isDesktop && window.attachHover) window.attachHover();
    }

    function restoreSession(sessionId) {
        var found = null;
        for (var i = 0; i < sessions.length; i++) {
            if (sessions[i].id === sessionId) { found = sessions[i]; break; }
        }
        if (!found) return;

        saveSession();

        curSession = found.id;
        feedBlocks = found.blocks.slice();

        viewLanding.classList.remove('active');
        document.body.classList.remove('typing');
        if (typingTimer) clearTimeout(typingTimer);
        feedContainer.innerHTML = '';

        viewResults.classList.add('active');
        historyTrack.classList.remove('hidden');
        renderHistoryDots();

        for (var i = 0; i < feedBlocks.length; i++) {
            var bd = feedBlocks[i];
            var block = document.createElement('div');
            block.className = 'feed-block visible';
            block.id = bd.id;

            var safe = escapeHtml(bd.query);
            block.innerHTML =
                '<div class="query-huge">' + safe + '</div>' +
                '<div class="sources-strip">' +
                '<div class="strip-label">REF //</div>' +
                '<div class="strip-items">' +
                '</div>' +
                '</div>' +
                '<div class="answer-block"></div>';

            feedContainer.appendChild(block);
            cleanOldSourceBadges(block);
        }

        setTimeout(function () {
            viewResults.scrollTop = viewResults.scrollHeight;
        }, 100);
    }

    brandBtn.addEventListener('click', function () {
        saveSession();
        curSession = Date.now();

        if (typingTimer) clearTimeout(typingTimer);
        viewResults.classList.remove('active');
        historyTrack.classList.add('hidden');

        setTimeout(function () {
            mainInput.value = '';
            mirrorText.textContent = '';
            hintText.classList.remove('visible');
            feedContainer.innerHTML = '';
            feedBlocks = [];
            viewLanding.classList.add('active');
            setTimeout(function () { mainInput.focus(); }, 800);
        }, 800);
    });

    menuBtn.addEventListener('click', function () {
        renderSidebar();
        sidebarPanel.classList.add('open');
    });
    closeSidebarBtn.addEventListener('click', function () { sidebarPanel.classList.remove('open'); });

    mainInput.addEventListener('input', function () {
        var val = mainInput.value;
        if (val.length > 0) {
            document.body.classList.add('typing');
            hintText.classList.add('visible');
        } else {
            document.body.classList.remove('typing');
            hintText.classList.remove('visible');
        }
        mirrorText.textContent = val;
    });

    mainInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            var q = mainInput.value.trim();
            if (q.length > 0 && q.length < 500) {
                startNewFeed(q);
            }
        }
    });

    function startNewFeed(query) {
        saveSession();
        curSession = Date.now();

        document.body.classList.remove('typing');
        feedContainer.innerHTML = '';
        feedBlocks = [];

        viewLanding.classList.remove('active');

        setTimeout(function () {
            viewResults.classList.add('active');
            historyTrack.classList.remove('hidden');
            addBlock(query);
        }, 800);
    }

    function addBlock(query) {
        var id = 'block-' + Date.now();
        feedBlocks.push({ id: id, query: query });
        renderHistoryDots();

        var safe = escapeHtml(query);

        var block = document.createElement('div');
        block.className = 'feed-block';
        block.id = id;

        block.innerHTML =
            '<div class="query-huge">' + safe + '</div>' +
            '<div class="sources-strip">' +
            '<div class="strip-label">REF //</div>' +
            '<div class="strip-items">' +
            '</div>' +
            '</div>' +
            '<div class="answer-block"></div>';

        feedContainer.appendChild(block);

        setTimeout(function () {
            block.scrollIntoView({ behavior: 'smooth', block: 'start' });
            block.classList.add('visible');
            if (isDesktop && window.attachHover) window.attachHover();
        }, 100);

        setTimeout(function () {
            fetchAnswer(block, query);
        }, 1100);
    }

    function renderSources(block, sources) {
        var items = block.querySelector('.strip-items');
        if (!items) return;
        if (!sources || sources.length === 0) {
            items.innerHTML = '';
            return;
        }
        var html = '';
        for (var i = 0; i < sources.length; i++) {
            var s = sources[i];
            var host = 'source';
            try { host = new URL(s.url).hostname.replace(/^www\./, ''); } catch (e) {}
            html += '<a class="source-item" href="' + escapeHtml(s.url) + '" target="_blank" rel="noreferrer">' +
                '<span class="source-index">' + (i + 1) + '</span>' +
                '<span>' + escapeHtml(host) + '</span>' +
                '</a>';
        }
        items.innerHTML = html;
        cleanOldSourceBadges(items);
        if (isDesktop && window.attachHover) window.attachHover();
    }

    function formatInlineMarkdown(text) {
        return escapeHtml(text)
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
            .replace(/\[(\d+)\]/g, '<span class="cite-num">[$1]</span>');
    }

    function renderAnswerMarkdown(text) {
        var lines = String(text || '').replace(/\r\n/g, '\n').split('\n');
        var html = '';
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (!line) continue;

            var heading = line.match(/^#{1,4}\s+(.+)$/);
            if (heading) {
                html += '<p><strong>' + formatInlineMarkdown(heading[1]) + '</strong></p>';
                continue;
            }

            var bullet = line.match(/^[-*]\s+(.+)$/);
            if (bullet) {
                html += '<p class="answer-bullet">' + formatInlineMarkdown(bullet[1]) + '</p>';
                continue;
            }

            html += '<p>' + formatInlineMarkdown(line) + '</p>';
        }
        return html || '<p>No answer returned.</p>';
    }

    function setStage(answer, message) {
        var clean = String(message || 'Working').replace(/\.+\s*$/, '');
        answer.innerHTML = '<p class="thinking-line"><span class="thinking-dots">' + escapeHtml(clean) + '</span></p>';
    }

    function fetchAnswer(block, query) {
        var answer = block.querySelector('.answer-block');
        renderSources(block, []);
        setStage(answer, 'Initializing research...');

        fetch('/api/ask/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: query, max_sources: 8 })
        })
            .then(function (r) {
                if (!r.ok) {
                    if (r.status === 429) throw new Error('rate_limited');
                    throw new Error('backend_status_' + r.status);
                }
                if (!r.body) throw new Error('Streaming is not supported in this browser');
                var reader = r.body.getReader();
                var decoder = new TextDecoder();
                var buffer = '';

                function pump() {
                    return reader.read().then(function (chunk) {
                        if (chunk.done) return;
                        buffer += decoder.decode(chunk.value, { stream: true });
                        var lines = buffer.split('\n');
                        buffer = lines.pop();
                        for (var i = 0; i < lines.length; i++) {
                            if (!lines[i].trim()) continue;
                            var event = JSON.parse(lines[i]);
                            if (event.type === 'stage') {
                                setStage(answer, event.message || 'Working...');
                            } else if (event.type === 'done') {
                                renderSources(block, event.sources || []);
                                typeAnswer(answer, renderAnswerMarkdown(event.answer || 'No answer returned.'));
                            } else if (event.type === 'error') {
                                throw new Error(event.message || 'Backend error');
                            }
                        }
                        return pump();
                    });
                }

                return pump();
            })
            .catch(function (err) {
                renderSources(block, []);
                var msg = String(err && err.message ? err.message : err);
                if (msg.indexOf('429') !== -1 || msg.indexOf('rate_limited') !== -1 || msg.indexOf('rate-limited') !== -1) {
                    typeAnswer(answer,
                        '<p>The research service is temporarily rate-limited.</p>' +
                        '<p>Use another API key or wait for the quota window to reset.</p>'
                    );
                } else {
                    typeAnswer(answer,
                        '<p>I could not reach the local AskKara backend.</p>' +
                        '<p>Start it with <strong>python backend.py</strong>, then try again.<span class="cite-num">[local]</span></p>' +
                        '<p style="font-size:0.8em; opacity:0.7;">' + escapeHtml(msg) + '</p>'
                    );
                }
            });
    }

    function typeAnswer(container, html) {
        container.innerHTML = '';
        window._pendingAnswer = html;

        var tmp = document.createElement('div');
        tmp.innerHTML = html;
        var paragraphs = tmp.querySelectorAll('p');
        var pi = 0;

        function doParagraph() {
            if (pi >= paragraphs.length) {
                var c = container.querySelector('.answer-typing-cursor');
                if (c) c.remove();
                viewResults.scrollBy({ top: 100, behavior: 'smooth' });
                return;
            }

            var p = document.createElement('p');
            container.appendChild(p);
            var fullHtml = paragraphs[pi].innerHTML;
            var ci = 0;
            var cursor = document.createElement('span');
            cursor.className = 'answer-typing-cursor';

            function tick() {
                if (ci >= fullHtml.length) {
                    if (cursor.parentNode === p) p.removeChild(cursor);
                    p.innerHTML = fullHtml;
                    pi++;
                    typingTimer = setTimeout(doParagraph, 100);
                    return;
                }

                if (fullHtml[ci] === '<') {
                    ci++;
                    while (ci < fullHtml.length && fullHtml[ci] !== '>') ci++;
                    if (ci < fullHtml.length) ci++;
                    p.innerHTML = fullHtml.substring(0, ci);
                    p.appendChild(cursor);
                    typingTimer = setTimeout(tick, 5);
                } else {
                    var nextStop = Math.min(fullHtml.length, ci + 5);
                    while (ci < nextStop && fullHtml[ci] !== '<') ci++;
                    p.innerHTML = fullHtml.substring(0, ci);
                    p.appendChild(cursor);

                    if (ci % 25 === 0) viewResults.scrollBy(0, 8);

                    var delay = 3;
                    var ch = fullHtml[ci - 1];
                    if (ch === '.' || ch === '!' || ch === '?') delay = 25;
                    typingTimer = setTimeout(tick, delay);
                }
            }
            tick();
        }
        doParagraph();
    }

    followupInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && followupInput.value.trim()) {
            var q = followupInput.value.trim();
            if (q.length === 0 || q.length > 500) return;
            followupInput.value = '';

            if (typingTimer) {
                clearTimeout(typingTimer);
                typingTimer = null;
                var cursors = document.querySelectorAll('.answer-typing-cursor');
                for (var i = 0; i < cursors.length; i++) cursors[i].remove();

                if (feedBlocks.length > 0) {
                    var lastId = feedBlocks[feedBlocks.length - 1].id;
                    var lastEl = document.getElementById(lastId);
                    if (lastEl) {
                        var ab = lastEl.querySelector('.answer-block');
                        if (ab && window._pendingAnswer) {
                            ab.innerHTML = window._pendingAnswer;
                        }
                    }
                }
            }

            addBlock(q);
            followupInput.blur();
            setTimeout(function () { followupInput.focus(); }, 1200);
        }
    });

    function renderHistoryDots() {
        var html = '';
        for (var i = 0; i < feedBlocks.length; i++) {
            var cls = (i === feedBlocks.length - 1) ? ' active' : '';
            var title = escapeHtml(feedBlocks[i].query);
            html += '<div class="hist-dot' + cls + '" data-target="' + feedBlocks[i].id + '" data-title="' + title + '"></div>';
        }
        historyTrack.innerHTML = html;

        var dots = document.querySelectorAll('.hist-dot');
        for (var j = 0; j < dots.length; j++) {
            dots[j].addEventListener('click', function () {
                var tid = this.getAttribute('data-target');
                var el = document.getElementById(tid);
                if (el) {
                    var all = document.querySelectorAll('.hist-dot');
                    for (var k = 0; k < all.length; k++) all[k].classList.remove('active');
                    this.classList.add('active');
                    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        }

        if (isDesktop && window.attachHover) window.attachHover();
    }

    var observer = new IntersectionObserver(function (entries) {
        var visible = [];
        for (var i = 0; i < entries.length; i++) {
            if (entries[i].isIntersecting) visible.push(entries[i].target.id);
        }

        if (visible.length > 0) {
            var dots = document.querySelectorAll('.hist-dot');
            for (var j = 0; j < dots.length; j++) {
                dots[j].classList.toggle('active', dots[j].getAttribute('data-target') === visible[0]);
            }
        }
    }, { root: viewResults, threshold: 0.3 });

    var _origAppend = feedContainer.appendChild.bind(feedContainer);
    feedContainer.appendChild = function (el) {
        _origAppend(el);
        observer.observe(el);
    };

    setTimeout(function () { mainInput.focus(); }, 1000);

    var themeBtn = document.getElementById('themeToggle');
    if (themeBtn) {
        themeBtn.addEventListener('click', function () {
            var root = document.documentElement;
            var isLight = root.getAttribute('data-theme') === 'light';
            if (isLight) {
                root.removeAttribute('data-theme');
                localStorage.setItem('kara_theme', 'dark');
            } else {
                root.setAttribute('data-theme', 'light');
                localStorage.setItem('kara_theme', 'light');
            }
        });
    }

})();
