export class WebSocketManager {
    constructor(url, handlers) {
      this.url = url;
      this.handlers = handlers;
      this.reconnectAttempts = 0;
      this.maxReconnectAttempts = 5;
      this.reconnectInterval = 3000;
      this.socket = null;
    }
  
    connect() {
      this.socket = new WebSocket(this.url);
  
      this.socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.handlers.onOpen?.();
      };
  
      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handlers.onMessage?.(data);
        } catch (error) {
          this.handlers.onError?.(error);
        }
      };
  
      this.socket.onclose = (event) => {
        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
          setTimeout(() => {
            this.reconnectAttempts++;
            this.connect();
          }, this.reconnectInterval);
        }
        this.handlers.onClose?.(event);
      };
  
      this.socket.onerror = (error) => {
        this.handlers.onError?.(error);
      };
    }
  
    send(data) {
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify(data));
        return true;
      }
      return false;
    }
  
    disconnect() {
      this.socket?.close();
    }
  }