window.__ModuleLoader__.load({
  id: '@local/dsh-paper-research-coach',
  factory: (require) => {
    const React = require('react');
    const h = React.createElement;
    const PANEL = 'paper-research-coach';
    const icon = h('svg', {viewBox: '0 0 24 24', width: 20, height: 20, fill: 'none', stroke: 'currentColor', strokeWidth: 1.6},
      h('path', {d: 'M12 5c-3-2-6-2-10-1v15c4-1 7-1 10 1 3-2 6-2 10-1V4c-4-1-7-1-10 1ZM12 5v15M5 8h4M5 11h4M15 8h4M15 11h4'}));
    function Workbench() {
      return h('iframe', {
        title: 'Paper Research Coach · 论文研读',
        src: '/paper-research-coach/',
        allow: 'clipboard-read; clipboard-write',
        style: {border: 0, width: '100%', height: '100%', display: 'block', flex: 1, minHeight: 0, background: 'var(--dsw-alias-bg-base, #faf9f6)'},
      });
    }
    return {
      inject: ['slots'],
      apply(ctx) {
        ctx.slots.inject('main', () => ctx.slots.register({name: 'main', key: PANEL}, Workbench));
        function Nav(props) {
          return icon;
        }
        ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({name: 'sidebar.panellist', id: PANEL, order: 55, label: () => '论文研读'}, Nav));
      },
    };
  },
});
