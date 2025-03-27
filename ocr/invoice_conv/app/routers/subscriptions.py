from typing import Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, Response
from sqlalchemy.orm import Session
import stripe

from app.core.deps import get_db, get_current_user, get_current_active_superuser
from app.core.config import settings
from app.services import subscription as subscription_service
from app.models.user import User
from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionOut, SubscriptionUpdate, SubscriptionCreate


router = APIRouter()

# Initialize Stripe if keys are provided
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


@router.get("/", response_model=SubscriptionOut)
def get_current_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get current user's subscription."""
    subscription = subscription_service.get_user_subscription(db, current_user.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription


@router.post("/upgrade", response_model=SubscriptionOut)
def upgrade_subscription(
    *,
    db: Session = Depends(get_db),
    tier: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Upgrade subscription to a different tier."""
    # Validate tier
    valid_tiers = ["free", "basic", "pro", "enterprise"]
    if tier not in valid_tiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier. Must be one of: {', '.join(valid_tiers)}",
        )
    
    # Get current subscription
    subscription = subscription_service.get_user_subscription(db, current_user.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Check if downgrading to free tier (immediate)
    if tier == "free":
        # Update subscription
        subscription_update = SubscriptionUpdate(
            tier=tier,
            monthly_scans=settings.FREE_TIER_SCANS,
            scans_used=0,  # Reset usage on downgrade
        )
        updated_subscription = subscription_service.update_subscription(
            db, subscription, subscription_update
        )
        return updated_subscription
    
    # For paid tiers, in a real app we would redirect to Stripe Checkout
    # Here we'll just simulate payment and upgrade
    
    # Set monthly scans based on tier
    monthly_scans = settings.FREE_TIER_SCANS
    if tier == "basic":
        monthly_scans = settings.BASIC_TIER_SCANS
    elif tier == "pro":
        monthly_scans = settings.PRO_TIER_SCANS
    elif tier == "enterprise":
        monthly_scans = settings.ENTERPRISE_TIER_SCANS
    
    # Update subscription (in real app, this would happen after payment confirmation)
    subscription_update = SubscriptionUpdate(
        tier=tier,
        monthly_scans=monthly_scans,
        scans_used=0,  # Reset usage on upgrade
    )
    updated_subscription = subscription_service.update_subscription(
        db, subscription, subscription_update
    )
    
    return updated_subscription


@router.post("/create-checkout-session")
def create_checkout_session(
    *,
    db: Session = Depends(get_db),
    tier: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a Stripe checkout session for subscription upgrade."""
    # Ensure Stripe is configured
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PUBLISHABLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Stripe payments not configured",
        )
    
    # Validate tier
    valid_tiers = ["basic", "pro", "enterprise"]
    if tier not in valid_tiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier. Must be one of: {', '.join(valid_tiers)}",
        )
    
    # Set price ID based on tier (these would be real Stripe price IDs in production)
    price_id = "price_mock"  # Mock for demonstration
    tier_names = {
        "basic": "Basic",
        "pro": "Professional",
        "enterprise": "Enterprise",
    }
    
    # Create checkout session
    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=current_user.email,
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            mode="subscription",
            success_url="http://localhost:8000/subscription/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost:8000/subscription/cancel",
            metadata={
                "user_id": current_user.id,
                "tier": tier,
            },
        )
        return {"checkout_url": checkout_session.url}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating checkout session: {str(e)}",
        )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def webhook_received(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Any:
    """Handle Stripe webhook events."""
    # Ensure Stripe is configured
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        return {"status": "ignored"}
    
    # Get request body
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    # Verify webhook signature
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle specific events
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        background_tasks.add_task(handle_subscription_created, db, session)
    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        background_tasks.add_task(handle_subscription_updated, db, subscription)
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        background_tasks.add_task(handle_subscription_deleted, db, subscription)
    
    return {"status": "success"}


async def handle_subscription_created(db: Session, session) -> None:
    """Background task to handle subscription creation."""
    # Get user ID and tier from metadata
    user_id = session["metadata"]["user_id"]
    tier = session["metadata"]["tier"]
    
    # Set monthly scans based on tier
    monthly_scans = settings.FREE_TIER_SCANS
    if tier == "basic":
        monthly_scans = settings.BASIC_TIER_SCANS
    elif tier == "pro":
        monthly_scans = settings.PRO_TIER_SCANS
    elif tier == "enterprise":
        monthly_scans = settings.ENTERPRISE_TIER_SCANS
    
    # Get current subscription
    subscription = subscription_service.get_user_subscription(db, user_id)
    if not subscription:
        return
    
    # Update subscription
    subscription_update = SubscriptionUpdate(
        tier=tier,
        monthly_scans=monthly_scans,
        scans_used=0,  # Reset usage on new subscription
        stripe_customer_id=session["customer"],
        stripe_subscription_id=session["subscription"],
    )
    subscription_service.update_subscription(db, subscription, subscription_update)


async def handle_subscription_updated(db: Session, subscription_data) -> None:
    """Background task to handle subscription updates."""
    # Get internal subscription by Stripe subscription ID
    subscriptions = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_data["id"]
    ).all()
    
    for subscription in subscriptions:
        # Update status based on Stripe status
        status = "active"
        if subscription_data["status"] == "canceled":
            status = "cancelled"
        elif subscription_data["status"] == "unpaid":
            status = "pastdue"
        
        # Update subscription
        subscription_update = SubscriptionUpdate(status=status)
        subscription_service.update_subscription(db, subscription, subscription_update)


async def handle_subscription_deleted(db: Session, subscription_data) -> None:
    """Background task to handle subscription deletions."""
    # Get internal subscription by Stripe subscription ID
    subscriptions = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_data["id"]
    ).all()
    
    for subscription in subscriptions:
        # Downgrade to free tier
        subscription_update = SubscriptionUpdate(
            tier="free",
            status="active",
            monthly_scans=settings.FREE_TIER_SCANS,
            scans_used=0,  # Reset usage on downgrade
            stripe_subscription_id=None,
        )
        subscription_service.update_subscription(db, subscription, subscription_update)
