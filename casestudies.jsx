/* CaseStudiesView — interface for simulating custom scenarios */

function CaseStudiesView({
  activeSpeakerId, utterances, focusedId, voteTally, onFocus, onClearFocus,
  roundDividers, currentRound, totalRounds, connectionStatus, connectionError, debateStep,
  debateHistory, onLoadHistory, onStartLive, isRunning
}) {
  const [customTitle, setCustomTitle] = React.useState('Alien Tech Discovery');
  const [customDesc, setCustomDesc] = React.useState('A crashed UFO containing advanced propulsion technology has been discovered in Antarctica. Nations are debating whether to share the technology globally or secure it for exclusive use.');
  const [customAction, setCustomAction] = React.useState('MULTILATERAL_INTERVENTION');

  const handleSimulate = () => {
    if (!customTitle.trim() || !customDesc.trim() || !customAction.trim()) return;
    onStartLive({
      crisisType: 'custom_scenario',
      crisisDescription: customDesc,
      mappoAction: customAction
    });
  };

  return React.createElement('div', {
    style: {
      flex: 1, display: 'grid', gridTemplateColumns: '400px 1fr', gap: 24, minHeight: 0,
      padding: '24px 32px', background: 'radial-gradient(ellipse at 50% 80%, rgba(59,130,246,0.04) 0%, #050810 60%)',
    }
  },
    // Left sidebar: Custom Scenario Form
    React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 16 } },
      React.createElement('div', {
        style: {
          background: 'var(--glass-bg)', backdropFilter: 'var(--glass-blur)',
          border: '1px solid var(--glass-border)', borderRadius: 16,
          boxShadow: 'var(--shadow-glass)', padding: 20,
        }
      },
        React.createElement('div', { style: { fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,0.8)', letterSpacing: '1px', marginBottom: 16 } },
          'CUSTOM SCENARIO CREATOR'
        ),
        React.createElement('div', { style: { marginBottom: 12 } },
          React.createElement('label', { style: { display: 'block', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.4)', marginBottom: 6 } }, 'SCENARIO TITLE'),
          React.createElement('input', {
            type: 'text',
            value: customTitle,
            onChange: e => setCustomTitle(e.target.value),
            style: {
              width: '100%', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8, padding: '10px 12px', color: '#fff', fontFamily: 'var(--font-ui)', fontSize: 13,
              boxSizing: 'border-box'
            }
          })
        ),
        React.createElement('div', { style: { marginBottom: 12 } },
          React.createElement('label', { style: { display: 'block', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.4)', marginBottom: 6 } }, 'PROPOSED ACTION (What they debate)'),
          React.createElement('input', {
            type: 'text',
            value: customAction,
            onChange: e => setCustomAction(e.target.value),
            style: {
              width: '100%', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8, padding: '10px 12px', color: '#fff', fontFamily: 'var(--font-ui)', fontSize: 13,
              boxSizing: 'border-box'
            }
          })
        ),
        React.createElement('div', { style: { marginBottom: 20 } },
          React.createElement('label', { style: { display: 'block', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.4)', marginBottom: 6 } }, 'SCENARIO DESCRIPTION (PROMPT)'),
          React.createElement('textarea', {
            value: customDesc,
            onChange: e => setCustomDesc(e.target.value),
            rows: 6,
            style: {
              width: '100%', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8, padding: '10px 12px', color: '#fff', fontFamily: 'var(--font-ui)', fontSize: 13,
              boxSizing: 'border-box', resize: 'none', lineHeight: 1.5
            }
          })
        ),
        React.createElement('button', {
          onClick: handleSimulate,
          disabled: isRunning,
          className: 'btn-skeu',
          style: {
            width: '100%', padding: '12px 0', fontSize: 12, fontWeight: 600,
            borderColor: 'rgba(139,92,246,0.5)', color: 'rgba(200,180,255,0.9)',
            background: 'linear-gradient(180deg, rgba(139,92,246,0.1) 0%, rgba(139,92,246,0.02) 100%)',
            opacity: isRunning ? 0.5 : 1
          }
        }, isRunning ? 'DEBATE IN PROGRESS...' : '▶ SIMULATE CUSTOM DEBATE (MAPPO)')
      ),
      React.createElement('div', {
        style: {
          background: 'var(--glass-bg)', backdropFilter: 'var(--glass-blur)',
          border: '1px solid var(--glass-border)', borderRadius: 16,
          boxShadow: 'var(--shadow-glass)', padding: 16,
        }
      },
        React.createElement('div', { style: { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.5)', lineHeight: 1.5 } },
          'The custom description is fed directly to the trained LLM agents as their world context. They will generate live, dynamic responses based on their trained reward functions and relationships.'
        )
      )
    ),
    // Right area: Debate Transcript
    React.createElement('div', { style: { display: 'flex', minHeight: 0 } },
      React.createElement(DebateTranscriptPanel, {
        utterances, activeSpeakerId, focusedId, voteTally, onClearFocus,
        roundDividers, currentRound, totalRounds, connectionStatus, connectionError, debateStep,
        debateHistory, onLoadHistory,
      })
    )
  );
}

Object.assign(window, { CaseStudiesView });
