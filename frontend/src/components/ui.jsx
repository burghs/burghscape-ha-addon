import { theme, cx, getTone, toneBg, toneText, toneTextDark } from '../theme';


export const BRAND_LOGO_SRC = '/static/brand/burghscape-shield.svg';

export function BrandLogo({ className = '', imageClassName = '', showText = true, subtitle = 'MyBeacon Portal' }) {
  return (
    <div className={cx('flex items-center gap-3', className)}>
      <img
        src={BRAND_LOGO_SRC}
        alt="Burghscape"
        className={cx('block shrink-0 object-contain', imageClassName)}
      />
      {showText && (
        <div className="min-w-0 leading-tight">
          <div className="truncate text-base font-semibold tracking-tight text-white">Burghscape</div>
          {subtitle && <div className="truncate text-[0.68rem] font-medium uppercase tracking-[0.16em] text-muted-text">{subtitle}</div>}
        </div>
      )}
    </div>
  );
}

export function Card({ children, className = '', compact = false, muted = false, as: Component = 'div', ...props }) {
  const cardClass = muted ? theme.surface.cardMuted : compact ? theme.surface.cardCompact : theme.surface.card;
  return <Component className={cx(cardClass, className)} {...props}>{children}</Component>;
}

export function Button({ children, variant = 'primary', className = '', as: Component = 'button', ...props }) {
  const buttonClass = theme.button[variant] || theme.button.primary;
  const buttonProps = Component === 'button' && props.type == null ? { type: 'button' } : {};
  return <Component className={cx(buttonClass, className)} {...buttonProps} {...props}>{children}</Component>;
}

export function Input({ className = '', ...props }) {
  return <input className={cx(theme.form.inputDark, className)} {...props} />;
}

export function Select({ className = '', children, ...props }) {
  return <select className={cx(theme.form.inputDark, className)} {...props}>{children}</select>;
}

export function Textarea({ className = '', ...props }) {
  return <textarea className={cx(theme.form.inputDark, className)} {...props} />;
}

export function Badge({ children, variant = 'neutral', light = false, className = '' }) {
  const palette = light ? theme.badgeLight : theme.badge;
  const badgeClass = palette[variant] || palette.neutral;
  return <span className={cx(badgeClass, className)}>{children}</span>;
}

export function StatusBadge({ children, status, variant, light = false, className = '' }) {
  return <Badge variant={variant || getTone(status)} light={light} className={className}>{children ?? status}</Badge>;
}

export function StatusDot({ active, status, variant, size = 'sm', pulse = false, className = '' }) {
  const tone = variant || (active === true ? 'success' : active === false ? 'muted' : getTone(status));
  return <span className={cx('status-dot', `status-dot-${size}`, toneBg[tone] || toneBg.muted, pulse && 'animate-pulse', className)} />;
}

export function ProgressBar({ value = 0, max = 100, variant = 'primary', className = '' }) {
  const numericValue = Number(value) || 0;
  const numericMax = Number(max) || 100;
  const width = Math.max(0, Math.min(100, (numericValue / numericMax) * 100));
  return (
    <div className={cx('progress-track', className)}>
      <div className={cx('progress-fill', toneBg[variant] || toneBg.primary)} style={{ width: `${width}%` }} />
    </div>
  );
}

export function StatCard({ label, value, tone = 'primary', className = '' }) {
  return (
    <Card compact className={className}>
      <p className="text-sm font-medium text-gray-400">{label}</p>
      <p className={cx('text-3xl font-bold mt-2', toneTextDark[tone] || 'text-white')}>{value}</p>
    </Card>
  );
}

export function DataTable({ columns = [], children, empty, colSpan, className = '' }) {
  return (
    <div className={cx('modal-card max-w-full overflow-x-auto', className)}>
      <table className="min-w-[720px] w-full text-sm">
        {columns.length > 0 && (
          <thead className="table-head">
            <tr>
              {columns.map((column) => (
                <th key={column.key || column.label} className={cx('table-th', column.align === 'right' && 'text-right')}>
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody className="table-body">
          {children || (empty && <tr><td colSpan={colSpan || columns.length || 1} className="table-empty">{empty}</td></tr>)}
        </tbody>
      </table>
    </div>
  );
}

export function Modal({ children, className = '', maxWidth = 'max-w-md', onClose }) {
  return (
    <div className="modal-backdrop">
      <div className={cx('modal-card w-full max-w-[calc(100vw-1.5rem)]', maxWidth, className)}>
        {children}
      </div>
    </div>
  );
}

export function ActionLink({ children, variant = 'primary', className = '', as: Component = 'button', ...props }) {
  const tone = toneText[variant] || toneText.primary;
  const buttonProps = Component === 'button' && props.type == null ? { type: 'button' } : {};
  return <Component className={cx('action-link', tone, className)} {...buttonProps} {...props}>{children}</Component>;
}

export function PageHeader({ title, subtitle, meta, actions }) {
  return (
    <div className={theme.page.toolbar}>
      <div>
        <h1 className={theme.page.title}>{title}</h1>
        {subtitle && <p className={theme.page.subtitle}>{subtitle}</p>}
      </div>
      {(meta || actions) && (
        <div className="flex flex-wrap items-center gap-3">
          {meta}
          {actions}
        </div>
      )}
    </div>
  );
}

export function LiveStatus({ lastUpdated }) {
  return (
    <div className="flex items-center gap-3">
      {lastUpdated && <span className="text-xs text-gray-500">Updated {lastUpdated.toLocaleTimeString()}</span>}
      <div className="live-indicator"><StatusDot variant="success" size="sm" pulse />Live</div>
    </div>
  );
}

export function LoadingState({ label = 'Loading...' }) {
  return <div className={theme.state.loading}><div>{label}</div></div>;
}

export function ErrorState({ error }) {
  return <div className={theme.state.error}>Error: {error}</div>;
}

export function EmptyState({ children }) {
  return <div className={theme.state.empty}>{children}</div>;
}
