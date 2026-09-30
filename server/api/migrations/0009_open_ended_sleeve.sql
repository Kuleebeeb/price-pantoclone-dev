ALTER TABLE quotations
    DROP CONSTRAINT IF EXISTS quotations_product_key_known;

ALTER TABLE quotations
    ADD CONSTRAINT quotations_product_key_known CHECK (
        product_key IN ('flat','sleeve','opaque','gusset','roll','cover')
    );
