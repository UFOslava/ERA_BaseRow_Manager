import { describe, it, expect, beforeEach, vi } from 'vitest';
import { showToast, showLoadingToast } from '../src/main.js';

describe('Loading Toast & Progress Bar Engine', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="toast-container" class="toast-container"></div>';
    vi.useFakeTimers();
  });

  it('creates a loading toast with hourglass icon and progress bar', () => {
    const toastHandle = showLoadingToast('Loading test data...', 25);
    expect(toastHandle).not.toBeNull();
    
    const toastEl = document.querySelector('.toast.loading');
    expect(toastEl).not.toBeNull();
    expect(toastEl.querySelector('.toast-hourglass')).not.toBeNull();
    expect(toastEl.querySelector('.toast-text').textContent).toBe('Loading test data...');
    
    const bar = toastEl.querySelector('.toast-progress-bar');
    expect(bar).not.toBeNull();
    expect(bar.style.width).toBe('25%');
    expect(bar.classList.contains('indeterminate')).toBe(false);
  });

  it('creates an indeterminate progress bar when no percentage is provided', () => {
    const toastHandle = showLoadingToast('Indeterminate loading...');
    const bar = toastHandle.element.querySelector('.toast-progress-bar');
    expect(bar.classList.contains('indeterminate')).toBe(true);
  });

  it('updates progress percentage and message', () => {
    const toastHandle = showLoadingToast('Step 1...', 10);
    toastHandle.updateProgress(60, 'Step 2...');
    
    const toastEl = toastHandle.element;
    expect(toastEl.querySelector('.toast-text').textContent).toBe('Step 2...');
    const bar = toastEl.querySelector('.toast-progress-bar');
    expect(bar.style.width).toBe('60%');
    expect(bar.classList.contains('indeterminate')).toBe(false);
  });

  it('completes loading toast and dismisses automatically after delay', () => {
    const toastHandle = showLoadingToast('Loading...', 50);
    toastHandle.complete('Finished loading!');
    
    expect(toastHandle.element.querySelector('.toast-text').textContent).toBe('Finished loading!');
    expect(toastHandle.element.querySelector('.toast-progress-bar').style.width).toBe('100%');

    expect(document.querySelector('.toast.loading')).not.toBeNull();
    vi.advanceTimersByTime(700);
    expect(document.querySelector('.toast.loading')).toBeNull();
  });

  it('dismisses toast immediately when dismiss() is called', () => {
    const toastHandle = showLoadingToast('Loading...');
    expect(document.querySelector('.toast.loading')).not.toBeNull();
    
    toastHandle.dismiss();
    expect(document.querySelector('.toast.loading')).toBeNull();
  });
});
