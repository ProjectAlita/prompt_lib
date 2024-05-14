// Example test file for Cypress/e2e Organizations Library

describe('Organization Feature', () => {
  it('should load the organization page successfully', () => {
    cy.visit('/organizations');
    cy.contains('Organizations');
  });
});