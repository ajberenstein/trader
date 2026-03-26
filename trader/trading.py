"""Trading handler - place orders and manage trades."""

import logging
from typing import Optional, Dict, List
from .alpaca_connector import AlpacaConnector
from .models import OrderRequest, Order

logger = logging.getLogger(__name__)


class TradingHandler:
    """
    Handles order placement and trade management.
    Works with both paper and live accounts.
    """

    def __init__(self, connector: AlpacaConnector):
        """
        Initialize trading handler.

        Args:
            connector: Connected AlpacaConnector instance
        """
        self.connector = connector

    def place_order(self, order_request: OrderRequest) -> Optional[Order]:
        """
        Place an order.

        Args:
            order_request: OrderRequest with order details

        Returns:
            Order object if successful, None otherwise.

        Example:
            >>> req = OrderRequest(symbol='AAPL', quantity=10, side='buy')
            >>> order = handler.place_order(req)
            >>> print(f"Order {order.id} placed")
        """
        if not self.connector.is_connected or not self.connector.client:
            logger.warning(
                "Not connected to Alpaca. Call connector.connect() first."
            )
            return None

        try:
            # Validate order
            if order_request.quantity <= 0:
                raise ValueError("Quantity must be positive")
            
            if order_request.side not in ["buy", "sell"]:
                raise ValueError("Side must be 'buy' or 'sell'")

            # Place order
            order = self.connector.client.submit_order(
                symbol=order_request.symbol,
                qty=order_request.quantity,
                side=order_request.side,
                type=order_request.order_type,
                time_in_force=order_request.time_in_force,
                limit_price=order_request.limit_price,
                stop_price=order_request.stop_price,
            )

            result = Order(
                id=order.id,
                symbol=order.symbol,
                quantity=float(order.qty),
                side=order.side,
                order_type=order.order_type,
                status=order.status,
                filled_qty=float(order.filled_qty),
                filled_avg_price=float(order.filled_avg_price or 0),
                created_at=order.created_at,
                updated_at=order.updated_at,
            )

            logger.info(
                f"✅ Order placed: {order_request.side.upper()} "
                f"{order_request.quantity} {order_request.symbol} "
                f"(ID: {order.id})"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Error placing order: {str(e)}")
            return None

    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get order details by ID.

        Args:
            order_id: Order ID

        Returns:
            Order object or None if not found.
        """
        if not self.connector.is_connected or not self.connector.client:
            logger.warning(
                "Not connected to Alpaca. Call connector.connect() first."
            )
            return None

        try:
            order = self.connector.client.get_order(order_id)
            return Order(
                id=order.id,
                symbol=order.symbol,
                quantity=float(order.qty),
                side=order.side,
                order_type=order.order_type,
                status=order.status,
                filled_qty=float(order.filled_qty),
                filled_avg_price=float(order.filled_avg_price or 0),
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
        except Exception as e:
            logger.error(f"Error fetching order {order_id}: {str(e)}")
            return None

    def list_orders(
        self, status: str = "all", limit: int = 100
    ) -> Optional[List[Order]]:
        """
        List orders with optional filtering.

        Args:
            status: 'all', 'open', 'closed', 'pending_new', 'accepted', 
                   'pending_cancel', 'cancelled', 'expired', 'rejected', 'filled'
            limit: Maximum number of orders to return

        Returns:
            List of Order objects or None if error.
        """
        if not self.connector.is_connected or not self.connector.client:
            logger.warning(
                "Not connected to Alpaca. Call connector.connect() first."
            )
            return None

        try:
            orders = self.connector.client.list_orders(
                status=status, limit=limit
            )
            return [
                Order(
                    id=order.id,
                    symbol=order.symbol,
                    quantity=float(order.qty),
                    side=order.side,
                    order_type=order.order_type,
                    status=order.status,
                    filled_qty=float(order.filled_qty),
                    filled_avg_price=float(order.filled_avg_price or 0),
                    created_at=order.created_at,
                    updated_at=order.updated_at,
                )
                for order in orders
            ]
        except Exception as e:
            logger.error(f"Error listing orders: {str(e)}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled successfully, False otherwise.
        """
        if not self.connector.is_connected or not self.connector.client:
            logger.warning(
                "Not connected to Alpaca. Call connector.connect() first."
            )
            return False

        try:
            self.connector.client.cancel_order(order_id)
            logger.info(f"✅ Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {str(e)}")
            return False

    def place_limit_order(self, symbol: str, quantity: float, side: str, limit_price: float) -> Optional[Order]:
        """Place a limit order (GTC)."""
        req = OrderRequest(
            symbol=symbol, quantity=quantity, side=side,
            order_type="limit", limit_price=limit_price, time_in_force="gtc"
        )
        return self.place_order(req)

    def place_stop_order(self, symbol: str, quantity: float, side: str, stop_price: float) -> Optional[Order]:
        """Place a stop order (GTC)."""
        req = OrderRequest(
            symbol=symbol, quantity=quantity, side=side,
            order_type="stop", stop_price=stop_price, time_in_force="gtc"
        )
        return self.place_order(req)

    def place_bracket_order(
        self, symbol: str, quantity: float, side: str,
        take_profit_price: float, stop_loss_price: float
    ) -> Optional[Order]:
        """Place a bracket order (market entry + take-profit limit + stop-loss)."""
        if not self.connector.is_connected or not self.connector.client:
            return None
        try:
            order = self.connector.client.submit_order(
                symbol=symbol,
                qty=quantity,
                side=side,
                type="market",
                time_in_force="gtc",
                order_class="bracket",
                take_profit={"limit_price": take_profit_price},
                stop_loss={"stop_price": stop_loss_price},
            )
            return Order(
                id=order.id,
                symbol=order.symbol,
                quantity=float(order.qty),
                side=order.side,
                order_type=order.order_type,
                status=order.status,
                filled_qty=float(order.filled_qty),
                filled_avg_price=float(order.filled_avg_price or 0),
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
        except Exception as e:
            logger.error(f"Error placing bracket order: {str(e)}")
            return None

    def modify_order(
        self, order_id: str,
        qty: Optional[float] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Optional[Order]:
        """Replace/modify an open order."""
        if not self.connector.is_connected or not self.connector.client:
            return None
        try:
            kwargs: Dict = {}
            if qty is not None:
                kwargs["qty"] = qty
            if limit_price is not None:
                kwargs["limit_price"] = limit_price
            if stop_price is not None:
                kwargs["stop_price"] = stop_price
            order = self.connector.client.replace_order(order_id, **kwargs)
            return Order(
                id=order.id,
                symbol=order.symbol,
                quantity=float(order.qty),
                side=order.side,
                order_type=order.order_type,
                status=order.status,
                filled_qty=float(order.filled_qty),
                filled_avg_price=float(order.filled_avg_price or 0),
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
        except Exception as e:
            logger.error(f"Error modifying order {order_id}: {str(e)}")
            return None

    def buy(self, symbol: str, quantity: float) -> Optional[Order]:
        """
        Convenience method to buy shares.

        Args:
            symbol: Stock symbol
            quantity: Number of shares

        Returns:
            Order object if successful.
        """
        req = OrderRequest(
            symbol=symbol,
            quantity=quantity,
            side="buy",
            order_type="market",
        )
        return self.place_order(req)

    def sell(self, symbol: str, quantity: float) -> Optional[Order]:
        """
        Convenience method to sell shares.

        Args:
            symbol: Stock symbol
            quantity: Number of shares

        Returns:
            Order object if successful.
        """
        req = OrderRequest(
            symbol=symbol,
            quantity=quantity,
            side="sell",
            order_type="market",
        )
        return self.place_order(req)
