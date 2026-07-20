export const semantic = {
  primary: 'primary',
  secondary: 'secondary',
  success: 'success',
  warning: 'warning',
  danger: 'danger',
  info: 'info',
  muted: 'muted',
};

export const toneText = {
  primary: 'text-primary-textLight',
  secondary: 'text-secondary-textLight',
  success: 'text-success-textLight',
  warning: 'text-warning-textLight',
  danger: 'text-danger-textLight',
  info: 'text-info-textLight',
  muted: 'text-muted-textLight',
};

export const toneTextDark = {
  primary: 'text-primary-text',
  secondary: 'text-secondary-text',
  success: 'text-success-text',
  warning: 'text-warning-text',
  danger: 'text-danger-text',
  info: 'text-info-text',
  muted: 'text-muted-text',
};

export const toneBg = {
  primary: 'bg-primary',
  secondary: 'bg-secondary',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
  info: 'bg-info',
  muted: 'bg-muted',
};

export const toneSoftBg = {
  primary: 'bg-primary-soft',
  secondary: 'bg-secondary-soft',
  success: 'bg-success-soft',
  warning: 'bg-warning-soft',
  danger: 'bg-danger-soft',
  info: 'bg-info-soft',
  muted: 'bg-muted-soft',
};

export const statusTone = {
  active: 'success',
  inactive: 'danger',
  disabled: 'danger',
  online: 'success',
  offline: 'muted',
  open: 'warning',
  in_progress: 'info',
  completed: 'success',
  closed: 'muted',
  available: 'success',
  failed: 'danger',
  normal: 'warning',
  medium: 'warning',
  high: 'danger',
  low: 'muted',
  admin: 'info',
  viewer: 'muted',
  basic: 'muted',
  standard: 'primary',
  premium: 'info',
};

export function getTone(value, fallback = 'muted') {
  return statusTone[value] || fallback;
}

export const theme = {
  page: {
    shell: 'space-y-6',
    title: 'page-title',
    subtitle: 'page-subtitle',
    toolbar: 'page-toolbar',
  },
  surface: {
    card: 'app-card',
    cardCompact: 'app-card app-card-compact',
    cardMuted: 'app-card-muted',
    stat: 'stat-card',
    modal: 'modal-card',
  },
  form: {
    input: 'form-input',
    inputDark: 'form-input-dark',
    select: 'form-input',
    textarea: 'form-input',
    label: 'form-label',
    checkbox: 'form-checkbox',
  },
  button: {
    base: 'btn',
    primary: 'btn btn-primary',
    secondary: 'btn btn-secondary',
    success: 'btn btn-success',
    danger: 'btn btn-danger',
    warning: 'btn btn-warning',
    ghost: 'btn btn-ghost',
    link: 'btn-link',
  },
  badge: {
    base: 'badge',
    success: 'badge badge-success',
    warning: 'badge badge-warning',
    danger: 'badge badge-danger',
    info: 'badge badge-info',
    neutral: 'badge badge-neutral',
    muted: 'badge badge-neutral',
    secondary: 'badge badge-secondary',
    primary: 'badge badge-primary',
  },
  badgeLight: {
    success: 'badge badge-success-light',
    warning: 'badge badge-warning-light',
    danger: 'badge badge-danger-light',
    info: 'badge badge-info-light',
    neutral: 'badge badge-neutral-light',
    muted: 'badge badge-neutral-light',
    secondary: 'badge badge-secondary-light',
    primary: 'badge badge-primary-light',
  },
  state: {
    loading: 'loading-state',
    empty: 'empty-state',
    error: 'alert-error',
    success: 'alert-success',
  },
};

export function cx(...classes) {
  return classes.filter(Boolean).join(' ');
}
