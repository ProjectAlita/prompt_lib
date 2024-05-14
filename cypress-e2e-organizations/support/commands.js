// Custom commands to support Cypress/e2e Organizations Library tests

// Example custom command
cy.Commands.add('loginAsAdmin', () => {
  cy.visit('/login');
  cy.get('input[name=username]').type('admin');
  cy.get('input[name=password]').type('admin123');
  cy.get('form').submit();
});