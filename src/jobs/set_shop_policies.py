"""
Job 7: imposta le pagine legali dello store (Privacy, Termini, Rimborsi,
Spedizioni) via GraphQL shopPolicyUpdate. Da lanciare una tantum (o quando
si vogliono aggiornare i testi).

Uso:
    python -m src.jobs.set_shop_policies
"""
from src.clients.shopify_client import ShopifyClient

STORE_NAME = "our store"
CONTACT_EMAIL = "canadesino91@gmail.com"

POLICIES = {
    "SHIPPING_POLICY": f"""
<p>We work with fulfillment partners in the US and China, so shipping times vary by item.</p>
<ul>
<li><strong>Processing time:</strong> 1-3 business days before your order ships.</li>
<li><strong>Estimated delivery:</strong> 7-20 business days depending on the item and your location.</li>
<li>You'll receive a tracking number by email as soon as your order ships.</li>
<li>Delays can occasionally happen due to customs or high demand - we'll keep you updated if that happens.</li>
</ul>
<p>Questions about your order? Contact us at {CONTACT_EMAIL}.</p>
""",
    "REFUND_POLICY": f"""
<p>We want you to be happy with your purchase.</p>
<ul>
<li>You can request a return or exchange within <strong>30 days</strong> of delivery.</li>
<li>Items must be unused and in their original packaging.</li>
<li>If an item arrives damaged or defective, contact us within 7 days of delivery for a free replacement or full refund.</li>
<li>Refunds are issued to your original payment method within 5-10 business days of us receiving the returned item.</li>
<li>Return shipping costs are covered by the customer unless the item was damaged, defective, or incorrect.</li>
</ul>
<p>To start a return, email us at {CONTACT_EMAIL} with your order number.</p>
""",
    "PRIVACY_POLICY": f"""
<p>This Privacy Policy describes how {STORE_NAME} ("we", "us") collects, uses, and discloses your
personal information when you visit or make a purchase from our store.</p>

<h3>Information We Collect</h3>
<p>When you visit the site, we automatically collect certain information about your device,
including your browser, IP address, and time zone. When you make a purchase, we collect your
name, billing/shipping address, email address, phone number, and payment information.</p>

<h3>How We Use Your Information</h3>
<p>We use this information to fulfill orders, communicate with you, screen for fraud, and
(with your consent) send you marketing communications.</p>

<h3>Sharing Your Information</h3>
<p>We share your information with third parties who help us provide our services, including
payment processors (Shopify Payments, PayPal), our fulfillment partners, and shipping carriers,
only to the extent necessary to fulfill your order.</p>

<h3>Your Rights</h3>
<p>If you are a resident of the EU/EEA, you have the right to access, correct, or delete your
personal data. Contact us at {CONTACT_EMAIL} to exercise these rights.</p>

<h3>Contact</h3>
<p>Questions about this policy? Email us at {CONTACT_EMAIL}.</p>
""",
    "TERMS_OF_SERVICE": f"""
<h3>Overview</h3>
<p>This website is operated by {STORE_NAME}. By visiting our site and/or purchasing something
from us, you agree to be bound by the following terms and conditions.</p>

<h3>Products and Pricing</h3>
<p>We reserve the right to modify prices for our products at any time. We also reserve the
right to limit the quantities of any products that we offer.</p>

<h3>Accuracy of Information</h3>
<p>We are not responsible if information made available on this site is not accurate, complete,
or current. Product descriptions and images are for general reference and may vary slightly
from the actual item.</p>

<h3>Shipping and Delivery</h3>
<p>See our <a href="/policies/shipping-policy">Shipping Policy</a> for estimated delivery times.</p>

<h3>Returns and Refunds</h3>
<p>See our <a href="/policies/refund-policy">Refund Policy</a> for details.</p>

<h3>Governing Law</h3>
<p>These Terms of Service are governed by the laws of Italy.</p>

<h3>Contact</h3>
<p>Questions about the Terms of Service? Email us at {CONTACT_EMAIL}.</p>
""",
}


def set_all_policies() -> None:
    shopify = ShopifyClient()

    existing = shopify._graphql(
        "query { shop { shopPolicies { id type } } }", {}
    )["shop"]["shopPolicies"]
    id_by_type = {p["type"]: p["id"] for p in existing}

    for policy_type, body in POLICIES.items():
        result = shopify._graphql(
            """
            mutation shopPolicyUpdate($input: ShopPolicyInput!) {
              shopPolicyUpdate(shopPolicy: $input) {
                shopPolicy { id type }
                userErrors { field message }
              }
            }
            """,
            {"input": {"type": policy_type, "body": body.strip()}},
        )["shopPolicyUpdate"]

        if result["userErrors"]:
            print(f"  ! {policy_type}: errore {result['userErrors']}")
        else:
            print(f"  + {policy_type}: aggiornata")


if __name__ == "__main__":
    set_all_policies()
