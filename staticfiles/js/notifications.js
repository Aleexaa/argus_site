// static/js/notifications.js

class NotificationManager {
    constructor() {
        this.checkInterval = null;
        this.soundEnabled = this.getSoundPreference();
        this.lastCheckTime = null;
        this.audio = null;
        this.init();
    }

    init() {
        this.loadSound();
        this.startPolling();
        this.setupEventListeners();
        this.updateBadge();
    }

    loadSound() {
        try {
            this.audio = new Audio('/static/sounds/notification.mp3');
            this.audio.preload = 'auto';
        } catch(e) {
            console.log('Audio not supported');
        }
    }

    getSoundPreference() {
        return localStorage.getItem('notifications_sound_enabled') !== 'false';
    }

    setSoundPreference(enabled) {
        localStorage.setItem('notifications_sound_enabled', enabled);
        this.soundEnabled = enabled;
        this.updateSoundButton();
    }

    playSound() {
        if (this.soundEnabled && this.audio) {
            this.audio.currentTime = 0;
            this.audio.play().catch(e => console.log('Audio play failed:', e));
        }
    }

    showBrowserNotification(title, body, link) {
        if (Notification.permission === 'granted') {
            const notification = new Notification(title, {
                body: body,
                icon: '/static/images/logo.png',
                tag: 'crm-notification',
                requireInteraction: false
            });
            
            notification.onclick = () => {
                window.focus();
                if (link) window.location.href = link;
                notification.close();
            };
            
            setTimeout(() => notification.close(), 5000);
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission();
        }
    }

    showToast(message, type = 'info', link = null) {
        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            this.createToastContainer();
        }
        
        const toast = document.createElement('div');
        toast.className = `notification-toast notification-toast-${type}`;
        toast.innerHTML = `
            <div class="toast-icon">${this.getIconForType(type)}</div>
            <div class="toast-content">
                <div class="toast-message">${message}</div>
                ${link ? `<a href="${link}" class="toast-link">Перейти →</a>` : ''}
            </div>
            <button class="toast-close">&times;</button>
        `;
        
        toast.querySelector('.toast-close').onclick = () => toast.remove();
        if (link) {
            toast.querySelector('.toast-link').onclick = (e) => {
                e.preventDefault();
                window.location.href = link;
            };
        }
        
        document.getElementById('toast-container').appendChild(toast);
        
        setTimeout(() => {
            if (toast.parentNode) toast.remove();
        }, 8000);
    }

    getIconForType(type) {
        const icons = {
            'new_request': '🆕',
            'request_assigned': '👤',
            'status_changed': '🔄',
            'new_comment': '💬',
            'new_feedback': '📨',
            'new_candidate': '🎯',
            'system': '⚙️',
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️'
        };
        return icons[type] || '🔔';
    }

    createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.innerHTML = `
            <style>
                #toast-container {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 10000;
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                }
                .notification-toast {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    background: white;
                    border-radius: 12px;
                    padding: 12px 16px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
                    min-width: 300px;
                    max-width: 400px;
                    animation: slideIn 0.3s ease;
                    border-left: 4px solid #1E3A8A;
                }
                .notification-toast-new_request { border-left-color: #10B981; }
                .notification-toast-request_assigned { border-left-color: #3B82F6; }
                .notification-toast-status_changed { border-left-color: #F59E0B; }
                .notification-toast-new_comment { border-left-color: #8B5CF6; }
                .toast-icon { font-size: 24px; }
                .toast-content { flex: 1; }
                .toast-message { font-size: 14px; color: #333; margin-bottom: 4px; }
                .toast-link { font-size: 12px; color: #1E3A8A; text-decoration: none; }
                .toast-link:hover { text-decoration: underline; }
                .toast-close {
                    background: none;
                    border: none;
                    font-size: 20px;
                    cursor: pointer;
                    color: #999;
                    padding: 0 4px;
                }
                .toast-close:hover { color: #333; }
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
            </style>
        `;
        document.body.appendChild(container);
    }

    updateBadge() {
        fetch('/crm/api/notifications/check/')
            .then(response => response.json())
            .then(data => {
                const badge = document.getElementById('notification-badge');
                if (badge) {
                    const total = data.total_new || 0;
                    if (total > 0) {
                        badge.textContent = total > 99 ? '99+' : total;
                        badge.style.display = 'flex';
                    } else {
                        badge.style.display = 'none';
                    }
                }
            })
            .catch(error => console.error('Error updating badge:', error));
    }

    checkNotifications() {
        const params = new URLSearchParams();
        if (this.lastCheckTime) {
            params.append('last_check', this.lastCheckTime);
        }
        
        fetch(`/crm/api/notifications/check/?${params.toString()}`)
            .then(response => response.json())
            .then(data => {
                if (data.has_new_notifications) {
                    this.playSound();
                    this.updateBadge();
                    this.loadNotificationsList();
                    
                    if (data.new_internal > 0 && data.internal_notifications) {
                        data.internal_notifications.forEach(notif => {
                            this.showToast(notif.message, notif.type, notif.link);
                            if (Notification.permission === 'granted') {
                                this.showBrowserNotification(notif.title, notif.message, notif.link);
                            }
                        });
                    }
                }
                this.lastCheckTime = data.timestamp;
            })
            .catch(error => console.error('Error checking notifications:', error));
    }

    loadNotificationsList() {
        const container = document.getElementById('notifications-list');
        if (!container) return;
        
        fetch('/crm/api/notifications/')
            .then(response => response.json())
            .then(data => {
                if (data.internal_notifications && data.internal_notifications.length > 0) {
                    container.innerHTML = data.internal_notifications.map(notif => `
                        <div class="notification-item ${!notif.is_read ? 'unread' : ''}" data-id="${notif.id}">
                            <div class="notification-icon">${this.getIconForType(notif.type)}</div>
                            <div class="notification-content">
                                <div class="notification-title">${notif.title}</div>
                                <div class="notification-message">${notif.message}</div>
                                <div class="notification-time">${notif.created_at}</div>
                            </div>
                            ${!notif.is_read ? '<div class="notification-unread-dot"></div>' : ''}
                        </div>
                    `).join('');
                    
                    // Добавляем обработчики кликов
                    container.querySelectorAll('.notification-item').forEach(item => {
                        item.addEventListener('click', () => {
                            const notifId = item.dataset.id;
                            this.markAsRead(notifId);
                            const link = item.querySelector('a')?.href || 
                                        item.getAttribute('data-link');
                            if (link) window.location.href = link;
                        });
                    });
                } else {
                    container.innerHTML = '<div class="notifications-empty">Нет уведомлений</div>';
                }
                
                const unreadCount = data.internal_notifications.filter(n => !n.is_read).length;
                const badge = document.getElementById('notification-badge');
                if (badge && unreadCount > 0) {
                    badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
                    badge.style.display = 'flex';
                } else if (badge) {
                    badge.style.display = 'none';
                }
            })
            .catch(error => console.error('Error loading notifications:', error));
    }

    markAsRead(notificationId) {
        fetch(`/crm/api/notifications/mark/${notificationId}/`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    this.loadNotificationsList();
                    this.updateBadge();
                }
            })
            .catch(error => console.error('Error marking as read:', error));
    }

    markAllAsRead() {
        fetch('/crm/api/notifications/mark-all/', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    this.loadNotificationsList();
                    this.updateBadge();
                    this.showToast('Все уведомления отмечены как прочитанные', 'success');
                }
            })
            .catch(error => console.error('Error marking all as read:', error));
    }

    toggleSound() {
        this.setSoundPreference(!this.soundEnabled);
        this.showToast(`Звук уведомлений ${this.soundEnabled ? 'включен' : 'выключен'}`, 'info');
    }

    updateSoundButton() {
        const soundBtn = document.getElementById('toggle-sound-btn');
        if (soundBtn) {
            soundBtn.innerHTML = this.soundEnabled ? '🔊 Звук вкл' : '🔇 Звук выкл';
            soundBtn.classList.toggle('sound-off', !this.soundEnabled);
        }
    }

    setupEventListeners() {
        // Клик вне панели уведомлений
        document.addEventListener('click', (e) => {
            const panel = document.getElementById('notifications-panel');
            const btn = document.querySelector('.notifications-toggle');
            if (panel && btn && !btn.contains(e.target) && !panel.contains(e.target)) {
                panel.classList.remove('show');
            }
        });
        
        // Запрос разрешения на уведомления
        if (Notification.permission === 'default') {
            setTimeout(() => {
                if (confirm('Разрешить показывать уведомления?')) {
                    Notification.requestPermission();
                }
            }, 2000);
        }
    }

    startPolling() {
        if (this.checkInterval) clearInterval(this.checkInterval);
        this.checkInterval = setInterval(() => this.checkNotifications(), 10000);
        this.checkNotifications();
    }

    stopPolling() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
        }
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.notificationManager = new NotificationManager();
});

// Функции для использования в HTML
function toggleNotificationsPanel() {
    const panel = document.getElementById('notifications-panel');
    if (panel) {
        panel.classList.toggle('show');
        if (panel.classList.contains('show')) {
            window.notificationManager?.loadNotificationsList();
        }
    }
}

function markAllNotificationsRead() {
    window.notificationManager?.markAllAsRead();
}

function toggleNotificationSound() {
    window.notificationManager?.toggleSound();
}